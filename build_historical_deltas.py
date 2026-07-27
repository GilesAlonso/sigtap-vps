import ftplib
import os
import sys
import sqlite3
import argparse
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import process_sigtap_zip, DB_PATH, OUTPUT_DIR
from history import compute_diffs_between_dbs, insert_diffs, init_history_table

FTP_HOST = 'ftp2.datasus.gov.br'
FTP_DIR = '/pub/sistemas/tup/downloads/'
TEMP_DIR = os.path.join(OUTPUT_DIR, 'temp_history_build')

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def process_historical_files(limit=12, start_year=None):
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    logging.info(f"Conectando ao FTP DATASUS ({FTP_HOST})...")
    ftp = ftplib.FTP(FTP_HOST)
    ftp.login(user='anonymous', passwd='anonymous@datasus.gov.br')
    ftp.cwd(FTP_DIR)
    
    files = [f for f in ftp.nlst() if f.startswith('TabelaUnificada_') and f.endswith('.zip')]
    files.sort()
    
    if start_year:
        files = [f for f in files if f.split('_')[1][:4] >= str(start_year)]
        
    if limit and limit > 0 and len(files) > limit:
        logging.info(f"Selecionando as últimas {limit} competências de um total de {len(files)}...")
        files = files[-limit:]
    else:
        logging.info(f"Processando todas as {len(files)} competências encontradas...")

    prev_db_path = None
    total_diffs_recorded = 0

    from history import compute_diffs_between_dbs, insert_diffs, init_history_table, get_db_connection, copy_existing_history

    # Garantir a existência do banco final e tabela de histórico
    if not os.path.exists(DB_PATH):
        logging.warning("DB_PATH principal não encontrado. Será criado ao final do processo.")

    final_conn = get_db_connection(DB_PATH)
    init_history_table(final_conn)
    final_conn.close()

    for idx, zip_filename in enumerate(files):
        logging.info(f"[{idx+1}/{len(files)}] Baixando {zip_filename}...")
        local_zip = os.path.join(TEMP_DIR, zip_filename)
        
        with open(local_zip, 'wb') as f:
            ftp.retrbinary(f'RETR {zip_filename}', f.write)

        curr_db_path = os.path.join(TEMP_DIR, f"comp_{idx}.db")
        
        try:
            # Processa o zip diretamente para o curr_db_path temporário
            process_sigtap_zip(local_zip, target_db_path=curr_db_path)
        except Exception as e:
            logging.error(f"Erro ao processar {zip_filename}: {e}")
            if os.path.exists(local_zip): os.remove(local_zip)
            continue

        # Remove o zip local para economizar espaço em disco
        if os.path.exists(local_zip):
            os.remove(local_zip)

        # Se houver um banco anterior, calcula o diff
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
                logging.info(f"Inseridos {len(diffs)} registros de histórico no banco.")

            # Apaga prev_db_path
            if os.path.exists(prev_db_path):
                os.remove(prev_db_path)

        prev_db_path = curr_db_path

    # No final, o último curr_db_path torna-se o DB_PATH oficial (versão mais recente)
    if prev_db_path and os.path.exists(prev_db_path):
        if os.path.exists(DB_PATH):
            conn_final = get_db_connection(DB_PATH)
            conn_last = get_db_connection(prev_db_path)
            copy_existing_history(conn_final, conn_last)
            conn_final.close()
            conn_last.close()
            os.remove(DB_PATH)
        
        os.rename(prev_db_path, DB_PATH)

    ftp.quit()
    
    # Limpa diretório temp
    if os.path.exists(TEMP_DIR):
        for f in os.listdir(TEMP_DIR):
            os.remove(os.path.join(TEMP_DIR, f))
        os.rmdir(TEMP_DIR)

    logging.info(f"=== Processo Concluído com Sucesso ===")
    logging.info(f"Total de deltas históricos gravados: {total_diffs_recorded}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Script de carga do histórico retroativo do SIGTAP via FTP DATASUS.")
    parser.add_argument("--limit", type=int, default=12, help="Número de competências mais recentes para processar (0 para todas). Padrão: 12")
    parser.add_argument("--start-year", type=int, default=None, help="Ano inicial para filtrar (ex: 2024)")
    args = parser.parse_args()

    process_historical_files(limit=args.limit, start_year=args.start_year)
