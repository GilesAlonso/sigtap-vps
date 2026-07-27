import ftplib
import os
import sys
import shutil
import sqlite3

# Add the current directory to the path so we can import from app.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import process_sigtap_zip, OUTPUT_DIR, DB_PATH

FTP_HOST = 'ftp2.datasus.gov.br'
FTP_DIR = '/pub/sistemas/tup/downloads/'
LOCAL_FILENAME = 'TabelaUnificada_latest.zip'
VERSION_FILE = os.path.join(OUTPUT_DIR, 'version.txt')

def check_and_update_sigtap():
    print(f"[{FTP_HOST}] Conectando ao FTP DATASUS...")
    try:
        ftp = ftplib.FTP(FTP_HOST)
        ftp.login(user='anonymous', passwd='anonymous@datasus.gov.br')
        ftp.cwd(FTP_DIR)
        
        files = ftp.nlst()
        zip_files = [f for f in files if f.startswith('TabelaUnificada_') and f.endswith('.zip')]
        
        if not zip_files:
            print("Nenhum arquivo zip da Tabela Unificada encontrado no diretório.")
            ftp.quit()
            return

        zip_files.sort()
        latest_file = zip_files[-1]
        
        print(f"Último arquivo no FTP: {latest_file}")
        
        # Check current version
        current_version = None
        if os.path.exists(VERSION_FILE):
            with open(VERSION_FILE, 'r') as f:
                current_version = f.read().strip()
                
        if current_version == latest_file:
            print(f"O banco de dados já está atualizado com a versão: {current_version}")
            ftp.quit()
            return
            
        print(f"Nova versão detectada! Baixando {latest_file}...")
        
        # Download
        with open(LOCAL_FILENAME, 'wb') as f:
            ftp.retrbinary(f'RETR {latest_file}', f.write)
            
        ftp.quit()
        print("Download concluído. Iniciando o processamento em banco staging (zero downtime)...")
        
        staging_db = os.path.join(OUTPUT_DIR, 'sigtap_staging.db')
        snapshot_old_db = os.path.join(OUTPUT_DIR, 'sigtap_snapshot_old.db')

        if os.path.exists(staging_db): os.remove(staging_db)
        if os.path.exists(snapshot_old_db): os.remove(snapshot_old_db)

        # Passo A: Se o banco live já existir, mantemos um snapshot do antigo para diffs e copiamos para staging
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, staging_db)
            shutil.copy2(DB_PATH, snapshot_old_db)

        # Passo B: Todo o processamento pesado é feito ESTRITAMENTE dentro do staging_db
        process_sigtap_zip(LOCAL_FILENAME, target_db_path=staging_db)

        # Se tínhamos um snapshot antigo, calcula o delta entre snapshot_old_db e staging_db
        if os.path.exists(snapshot_old_db):
            try:
                from history import compute_diffs_between_dbs, insert_diffs, get_db_connection
                conn_old = get_db_connection(snapshot_old_db)
                conn_staging = get_db_connection(staging_db)

                diffs = compute_diffs_between_dbs(conn_old, conn_staging)
                if diffs:
                    insert_diffs(conn_staging, diffs)
                    print(f"{len(diffs)} alterações registradas no histórico do banco staging.")

                conn_old.close()
                conn_staging.close()
            except Exception as e:
                print(f"Aviso ao calcular deltas no staging: {e}")
            finally:
                if os.path.exists(snapshot_old_db):
                    os.remove(snapshot_old_db)

        # Habilita o modo WAL e pragmas no staging antes do swap
        from history import get_db_connection
        conn_final = get_db_connection(staging_db)
        conn_final.execute("PRAGMA journal_mode=WAL;")
        conn_final.execute("PRAGMA synchronous=NORMAL;")
        conn_final.commit()
        conn_final.close()

        # Passo C: Substituição atômica no nível do SO (Zero Downtime para o Gunicorn)
        os.replace(staging_db, DB_PATH)
        print("Substituição atômica realizada com sucesso! Banco ao vivo atualizado em milissegundos.")

        # Atualiza arquivo de versão
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(VERSION_FILE, 'w') as f:
            f.write(latest_file)
            
        # Remove o zip temporário
        if os.path.exists(LOCAL_FILENAME):
            os.remove(LOCAL_FILENAME)
            
    except ftplib.all_errors as e:
        print(f"Erro de FTP: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante a atualização: {e}")

if __name__ == "__main__":
    check_and_update_sigtap()
