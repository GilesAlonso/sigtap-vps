import ftplib
import os
import re

FTP_HOST = 'ftp2.datasus.gov.br'
FTP_DIR = '/pub/sistemas/tup/downloads/'
LOCAL_FILENAME = 'TabelaUnificada_latest.zip'

def download_latest_sigtap():
    print(f"Conectando ao FTP DATASUS: {FTP_HOST}...")
    try:
        # Connect to FTP
        ftp = ftplib.FTP(FTP_HOST)
        # Use anonymous login as per Datasus requirement
        ftp.login(user='anonymous', passwd='anonymous@datasus.gov.br')
        
        print(f"Navegando para o diretório: {FTP_DIR}")
        ftp.cwd(FTP_DIR)
        
        # List all files in the directory
        files = ftp.nlst()
        
        # Filter files that match the TabelaUnificada zip pattern
        # The pattern usually is: TabelaUnificada_YYYYMM_vYYMMDDHHMM.zip
        zip_files = [f for f in files if f.startswith('TabelaUnificada_') and f.endswith('.zip')]
        
        if not zip_files:
            print("Nenhum arquivo zip da Tabela Unificada encontrado no diretório.")
            ftp.quit()
            return

        # Sort files. Since they include YYYYMM in the name, alphabetical sort puts the latest at the end.
        zip_files.sort()
        latest_file = zip_files[-1]
        
        print(f"O arquivo mais recente encontrado é: {latest_file}")
        print(f"Iniciando o download para: {LOCAL_FILENAME}...")
        
        # Download the file in binary mode
        with open(LOCAL_FILENAME, 'wb') as f:
            ftp.retrbinary(f'RETR {latest_file}', f.write)
            
        ftp.quit()
        print(f"Download concluído com sucesso!")
        
    except ftplib.all_errors as e:
        print(f"Erro de FTP: {e}")
    except Exception as e:
        print(f"Ocorreu um erro inesperado: {e}")

if __name__ == "__main__":
    download_latest_sigtap()
