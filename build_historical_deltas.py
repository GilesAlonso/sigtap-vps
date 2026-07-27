import os
import sys
import argparse
import logging
import sqlite3

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import process_sigtap_zip, DB_PATH, OUTPUT_DIR
from history import compute_diffs_between_dbs, insert_diffs, init_history_table, get_db_connection, copy_existing_history
from ftp_utils import list_sigtap_zips, download_sigtap_file

TEMP_DIR = os.path.join(OUTPUT_DIR, 'temp_history_build')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def extract_comp(filename):
    parts = filename.split('_')
    if len(parts) >= 2 and len(parts[1]) >= 6:
        return parts[1][:6]
    return filename

def is_comp_in_history(conn, comp):
    if not comp: return False
    try:
        cur = conn.cursor()
        cnt = cur.execute("SELECT COUNT(*) FROM tb_historico_alteracoes WHERE competencia_para = ?", (str(comp),)).fetchone()[0]
        return cnt > 0
    except Exception:
        return False

def process_historical_files(limit=12, start_year=None):
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    logging.info("Buscando lista de arquivos ZIP no FTP DATASUS com tratamento de retentativas...")
    files = list_sigtap_zips(timeout=120, max_retries=10)
    
    if start_year:
        files = [f for f in files if extract_comp(f)[:4] >= str(start_year)]
        
    if limit and limit > 0 and len(files) > limit:
        logging.info(f"Selecionando as últimas {limit} competências de um total de {len(files)}...")
        files = files[-limit:]
    else:
        logging.info(f"Processando todas as {len(files)} competências encontradas...")

    # Garantir a existência do banco final e tabela de histórico
    final_conn = get_db_connection(DB_PATH) if os.path.exists(DB_PATH) else None
    if final_conn:
        init_history_table(final_conn)
        final_conn.close()

    prev_db_path = None
    total_diffs_recorded = 0

    for idx, zip_filename in enumerate(files):
        comp_curr = extract_comp(zip_filename)
        comp_next = extract_comp(files[idx+1]) if (idx + 1 < len(files)) else None

        # Verificação de Retomada Inteligente (Resume Mode)
        if os.path.exists(DB_PATH):
            conn_check = get_db_connection(DB_PATH)
            curr_recorded = is_comp_in_history(conn_check, comp_curr)
            next_recorded = is_comp_in_history(conn_check, comp_next) if comp_next else True
            conn_check.close()

            if curr_recorded and next_recorded:
                logging.info(f"[{idx+1}/{len(files)}] Competência {comp_curr} já registrada no histórico. Ignorando download (Resume Mode).")
                continue

        logging.info(f"[{idx+1}/{len(files)}] Processando competência {comp_curr} ({zip_filename})...")
        local_zip = os.path.join(TEMP_DIR, zip_filename)
        
        try:
            download_sigtap_file(zip_filename, local_zip, timeout=120, max_retries=10)
        except Exception as e:
            logging.error(f"Falha crítica ao baixar {zip_filename} após retentativas: {e}")
            continue

        curr_db_path = os.path.join(TEMP_DIR, f"comp_{comp_curr}.db")
        if os.path.exists(curr_db_path):
            os.remove(curr_db_path)
        
        try:
            # Processa o zip diretamente para curr_db_path temporário
            process_sigtap_zip(local_zip, target_db_path=curr_db_path)
        except Exception as e:
            logging.error(f"Erro ao processar conteúdo do ZIP {zip_filename}: {e}")
            if os.path.exists(local_zip): os.remove(local_zip)
            continue

        # Remove o zip local após extração para economizar disco
        if os.path.exists(local_zip):
            os.remove(local_zip)

        # Se houver um banco anterior na sequência, calcula o delta
        if prev_db_path and os.path.exists(prev_db_path):
            conn_prev = get_db_connection(prev_db_path)
            conn_curr = get_db_connection(curr_db_path)

            diffs = compute_diffs_between_dbs(conn_prev, conn_curr)
            
            conn_prev.close()
            conn_curr.close()

            if diffs:
                target_conn = get_db_connection(DB_PATH) if os.path.exists(DB_PATH) else get_db_connection(curr_db_path)
                insert_diffs(target_conn, diffs)
                target_conn.close()
                total_diffs_recorded += len(diffs)
                logging.info(f"✓ {len(diffs)} registros de histórico gravados no banco de dados.")

            # Apaga o banco anterior da memória/disco
            if os.path.exists(prev_db_path):
                os.remove(prev_db_path)

        prev_db_path = curr_db_path

    # No final, o último curr_db_path torna-se o DB_PATH oficial (versão mais recente do SIGTAP)
    if prev_db_path and os.path.exists(prev_db_path):
        if os.path.exists(DB_PATH):
            conn_final = get_db_connection(DB_PATH)
            conn_last = get_db_connection(prev_db_path)
            copy_existing_history(conn_final, conn_last)
            conn_final.close()
            conn_last.close()
            os.remove(DB_PATH)
        
        os.rename(prev_db_path, DB_PATH)

    # Limpa diretório temporário se restou algo
    if os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            try:
                os.remove(os.path.join(TEMP_DIR, f))
            except Exception:
                pass
        try:
            os.rmdir(TEMP_DIR)
        except Exception:
            pass

    logging.info("=== Processo de Carga Histórica Concluído com Sucesso ===")
    logging.info(f"Total de deltas históricos gravados nesta sessão: {total_diffs_recorded}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script resiliente de carga do histórico retroativo do SIGTAP via FTP DATASUS.")
    parser.add_argument("--limit", type=int, default=12, help="Número de competências mais recentes para processar (0 para todas). Padrão: 12")
    parser.add_argument("--start-year", type=int, default=None, help="Ano inicial para filtrar (ex: 2008 ou 2024)")
    args = parser.parse_args()

    process_historical_files(limit=args.limit, start_year=args.start_year)
