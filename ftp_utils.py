import ftplib
import time
import logging

FTP_HOST = 'ftp2.datasus.gov.br'
FTP_DIR = '/pub/sistemas/tup/downloads/'

def connect_ftp(timeout=120, max_retries=10, delay=5):
    """Conecta ao FTP DATASUS com retentativas automáticas e timeout de socket configurável."""
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Conectando ao FTP DATASUS ({FTP_HOST}) [Tentativa {attempt}/{max_retries}]...")
            ftp = ftplib.FTP(FTP_HOST, timeout=timeout)
            ftp.login(user='anonymous', passwd='anonymous@datasus.gov.br')
            ftp.cwd(FTP_DIR)
            return ftp
        except Exception as e:
            logging.warning(f"Erro ao conectar ao FTP DATASUS (tentativa {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                raise e
            sleep_time = delay * (1.5 ** (attempt - 1))
            time.sleep(sleep_time)

def list_sigtap_zips(timeout=120, max_retries=10):
    """Lista todos os arquivos TabelaUnificada_*.zip do FTP com retentativas e reconexão."""
    for attempt in range(1, max_retries + 1):
        try:
            ftp = connect_ftp(timeout=timeout, max_retries=3)
            files = [f for f in ftp.nlst() if f.startswith('TabelaUnificada_') and f.endswith('.zip')]
            ftp.quit()
            files.sort()
            return files
        except Exception as e:
            logging.warning(f"Erro ao listar arquivos ZIP do FTP (tentativa {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                raise e
            time.sleep(5 * attempt)

def download_sigtap_file(remote_filename, local_path, timeout=120, max_retries=10):
    """Baixa um arquivo específico do FTP DATASUS com suporte a retentativas."""
    for attempt in range(1, max_retries + 1):
        try:
            logging.info(f"Baixando {remote_filename} [Tentativa {attempt}/{max_retries}]...")
            ftp = connect_ftp(timeout=timeout, max_retries=3)
            with open(local_path, 'wb') as f:
                ftp.retrbinary(f'RETR {remote_filename}', f.write)
            ftp.quit()
            return True
        except Exception as e:
            logging.warning(f"Erro ao baixar {remote_filename} (tentativa {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                raise e
            time.sleep(5 * attempt)
