import ftplib
import os
import sys

# Add the current directory to the path so we can import from app.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import process_sigtap_zip, OUTPUT_DIR

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
        print("Download concluído. Iniciando o processamento dos dados (isso pode levar alguns minutos)...")
        
        # Process the zip file to generate CSVs
        process_sigtap_zip(LOCAL_FILENAME)
        
        # Update version file
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(VERSION_FILE, 'w') as f:
            f.write(latest_file)
            
        print("Processamento concluído com sucesso! Banco de dados atualizado.")
        
        # Optional: remove the zip file to save space
        if os.path.exists(LOCAL_FILENAME):
            os.remove(LOCAL_FILENAME)
            
    except ftplib.all_errors as e:
        print(f"Erro de FTP: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante a atualização: {e}")

if __name__ == "__main__":
    check_and_update_sigtap()
