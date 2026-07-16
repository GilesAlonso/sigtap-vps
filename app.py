import os
import io
import csv
import pandas as pd
from zipfile import ZipFile, BadZipFile
from flask import Flask, render_template, request, redirect, url_for, jsonify
import logging
from werkzeug.utils import secure_filename
import shutil
import sqlite3

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'processed_data')
DB_PATH = os.path.join(OUTPUT_DIR, 'sigtap.db')
os.makedirs(OUTPUT_DIR, exist_ok=True)

def parse_single_layout_from_zip(zip_file, layout_filename):
    """Lê o arquivo de layout e retorna uma lista de (nome_coluna, start, end, tipo)"""
    column_specs = []
    with zip_file.open(layout_filename, 'r') as f:
        for line_bytes in f:
            line = line_bytes.decode('latin-1').strip()
            if not line: continue
            parts = line.split(',')
            if len(parts) >= 4:
                col_name = parts[0].strip()
                try:
                    tamanho = int(parts[1].strip())
                    start = int(parts[2].strip()) - 1
                    end = int(parts[3].strip())
                    tipo_str = parts[4].strip() if len(parts) > 4 else 'C'
                    
                    if tipo_str == 'NUMBER':
                        col_type = float if 'VL_' in col_name else int
                    else:
                        col_type = str
                        
                    column_specs.append((col_name, start, end, col_type))
                except ValueError:
                    logging.warning(f"Could not parse layout line: {line}")
    return column_specs

def process_sigtap_zip(zip_file_obj_or_path):
    """
    Extrai o ZIP do SIGTAP, converte para DataFrames e salva TUDO em um banco SQLite sigtap.db.
    Isso substitui a geração de múltiplos CSVs.
    """
    temp_db = os.path.join(OUTPUT_DIR, 'temp_sigtap.db')
    
    # Se já existir um temp db corrompido de uma run anterior, apaga
    if os.path.exists(temp_db):
        os.remove(temp_db)

    conn = sqlite3.connect(temp_db)
    
    try:
        with ZipFile(zip_file_obj_or_path, 'r') as z:
            zip_files_list = z.namelist()
            data_files = [f for f in zip_files_list if not f.lower().endswith('_layout.txt') and f.lower().endswith('.txt')]

            for data_filename in data_files:
                safe_name = secure_filename(os.path.basename(data_filename))
                if not safe_name or not safe_name.lower().endswith('.txt'):
                    continue

                table_name = safe_name.lower().replace('.txt', '')
                expected_layout_name = f"{table_name}_layout.txt"
                actual_layout_filename = next((f for f in zip_files_list if f.lower().endswith(expected_layout_name)), None)

                if not actual_layout_filename: continue
                column_specs = parse_single_layout_from_zip(z, actual_layout_filename)
                if not column_specs: continue

                data_rows = []
                with z.open(data_filename, 'r') as data_file:
                    for line_bytes in data_file:
                        line = line_bytes.decode('latin-1')
                        if not line.strip(): continue

                        row_data = {}
                        for col_name, start, end, col_type in column_specs:
                            value_str = line[start:end].strip()
                            if not value_str:
                                row_data[col_name] = None
                            elif col_type == int:
                                try:
                                    row_data[col_name] = int(value_str)
                                except ValueError:
                                    row_data[col_name] = None
                            elif col_type == float:
                                try:
                                    float_val = float(value_str)
                                    if col_name.upper() in ['VL_SA', 'VL_SH', 'VL_SP']:
                                        row_data[col_name] = float_val / 100.0
                                    else:
                                        row_data[col_name] = float_val
                                except ValueError:
                                    row_data[col_name] = None
                            else:
                                row_data[col_name] = value_str
                        data_rows.append(row_data)

                if data_rows:
                    df = pd.DataFrame(data_rows)
                    
                    if 'VL_SH' in df.columns and 'VL_SP' in df.columns:
                        df['VL_H'] = (df['VL_SH'].fillna(0) + df['VL_SP'].fillna(0)).round(2)
                        df = df.drop(columns=['VL_SH', 'VL_SP'])

                    # Salva direto no SQLite
                    df.to_sql(table_name, conn, if_exists='replace', index=False)

        conn.close()

        # Swap atômico: substitui o banco antigo pelo novo com sucesso garantido
        os.replace(temp_db, DB_PATH)
        logging.info("SQLite database built successfully!")

    except Exception as e:
        conn.close()
        if os.path.exists(temp_db):
            os.remove(temp_db)
        raise e

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if not os.path.exists(DB_PATH):
        return render_template('no_data.html')
    
    competencia_formatada = ""
    try:
        conn = get_db()
        row = conn.execute("SELECT DT_COMPETENCIA FROM tb_procedimento LIMIT 1").fetchone()
        if row and row['DT_COMPETENCIA']:
            dt_raw = str(row['DT_COMPETENCIA'])
            if len(dt_raw) == 6:
                competencia_formatada = f"{dt_raw[4:]}/{dt_raw[:4]}"
    except:
        pass

    return render_template('index.html', competencia=competencia_formatada)


@app.route('/api/filters')
def api_filters():
    if not os.path.exists(DB_PATH):
        return jsonify({})
    
    conn = get_db()
    filters = {}
    
    try:
        filters['financiamentos'] = [dict(row) for row in conn.execute("SELECT CO_FINANCIAMENTO, NO_FINANCIAMENTO FROM tb_financiamento")]
    except: filters['financiamentos'] = []
        
    try:
        filters['grupos'] = [dict(row) for row in conn.execute("SELECT CO_GRUPO, NO_GRUPO FROM tb_grupo")]
    except: filters['grupos'] = []
        
    try:
        filters['subgrupos'] = [dict(row) for row in conn.execute("SELECT CO_GRUPO, CO_SUB_GRUPO, NO_SUB_GRUPO FROM tb_sub_grupo")]
    except: filters['subgrupos'] = []
        
    try:
        filters['formas'] = [dict(row) for row in conn.execute("SELECT CO_GRUPO, CO_SUB_GRUPO, CO_FORMA_ORGANIZACAO, NO_FORMA_ORGANIZACAO FROM tb_forma_organizacao")]
    except: filters['formas'] = []

    return jsonify(filters)


@app.route('/api/procedimentos')
def api_procedimentos():
    if not os.path.exists(DB_PATH):
        return jsonify([])

    conn = get_db()
    query = "SELECT * FROM tb_procedimento WHERE 1=1"
    params = []

    # Basic Filters
    codigo = request.args.get('codigo', '')
    if codigo:
        query += " AND CO_PROCEDIMENTO LIKE ?"
        params.append(f"{codigo}%")
        
    nome = request.args.get('nome', '')
    if nome:
        query += " AND NO_PROCEDIMENTO LIKE ?"
        params.append(f"%{nome}%")
        
    complexidade = request.args.get('complexidade', '')
    if complexidade:
        query += " AND TP_COMPLEXIDADE = ?"
        params.append(complexidade[0] if len(complexidade) > 0 else "")
        
    financiamento = request.args.get('financiamento', '')
    if financiamento:
        query += " AND CO_FINANCIAMENTO = ?"
        params.append(financiamento)

    # Hierarchical Filters (Grupo -> Subgrupo -> Forma)
    grupo = request.args.get('grupo', '')
    subgrupos = request.args.getlist('subgrupo')
    formas = request.args.getlist('forma')
    
    # Remove empty strings from lists
    subgrupos = [s for s in subgrupos if s]
    formas = [f for f in formas if f]
    
    if grupo:
        hierarchical_conditions = []
        
        if not subgrupos:
            hierarchical_conditions.append(f"{grupo}%")
        else:
            for sub in subgrupos:
                if not formas:
                    hierarchical_conditions.append(f"{grupo}{sub}%")
                else:
                    for forma in formas:
                        hierarchical_conditions.append(f"{grupo}{sub}{forma}%")
        
        if hierarchical_conditions:
            clause = " OR ".join(["CO_PROCEDIMENTO LIKE ?"] * len(hierarchical_conditions))
            query += f" AND ({clause})"
            params.extend(hierarchical_conditions)

    # Advanced Filters
    sexo = request.args.get('sexo', '')
    if sexo:
        query += " AND TP_SEXO = ?"
        params.append(sexo)
        
    rubrica = request.args.get('rubrica', '')
    if rubrica:
        query += " AND CO_RUBRICA = ?"
        params.append(rubrica)
        
    idade_min = request.args.get('idade_min', '')
    if idade_min:
        query += " AND VL_IDADE_MINIMA >= ? AND VL_IDADE_MINIMA != 9999"
        params.append(idade_min)
        
    idade_max = request.args.get('idade_max', '')
    if idade_max:
        query += " AND VL_IDADE_MAXIMA <= ? AND VL_IDADE_MAXIMA != 9999"
        params.append(idade_max)
        
    pontos = request.args.get('pontos', '')
    if pontos:
        query += " AND QT_PONTOS = ? AND QT_PONTOS != 0"
        params.append(pontos)
        
    max_exec = request.args.get('max_exec', '')
    if max_exec:
        query += " AND QT_MAXIMA_EXECUCAO = ?"
        params.append(max_exec)
        
    tempo_perm = request.args.get('tempo_perm', '')
    if tempo_perm:
        query += " AND QT_TEMPO_PERMANENCIA = ? AND QT_TEMPO_PERMANENCIA != 9999"
        params.append(tempo_perm)

    # Execute and return
    rows = conn.execute(query, params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route('/procedimento/<codigo>')
def procedimento_detail(codigo):
    if not os.path.exists(DB_PATH):
        return "Banco de dados não encontrado.", 404
        
    conn = get_db()
    
    proc_principal = conn.execute("SELECT * FROM tb_procedimento WHERE CO_PROCEDIMENTO = ?", (codigo,)).fetchone()
    if not proc_principal:
        return f"Procedimento {codigo} não encontrado.", 404
    
    proc_principal = dict(proc_principal)
    
    descricao = None
    try:
        desc_row = conn.execute("SELECT DS_PROCEDIMENTO FROM tb_descricao WHERE CO_PROCEDIMENTO = ?", (codigo,)).fetchone()
        if desc_row:
            descricao = desc_row['DS_PROCEDIMENTO']
    except:
        pass

    related_data = {}
    
    # Busca dinamicamente todas as tabelas relacionais do SQLite
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rl_procedimento_%'").fetchall()
        
        for table_row in tables:
            rl_table = table_row['name']
            target_suffix = rl_table.replace('rl_procedimento_', '')
            target_tb = f"tb_{target_suffix}"
            
            # Descobre a chave primária da tabela alvo verificando suas colunas
            # Assumimos que a chave que liga a RL com a TB é a coluna que começa com CO_ e não é CO_PROCEDIMENTO
            columns_info = conn.execute(f"PRAGMA table_info({rl_table})").fetchall()
            key_column = next((col['name'] for col in columns_info if col['name'] != 'CO_PROCEDIMENTO' and col['name'].startswith('CO_')), None)
            
            if not key_column: continue
            
            # Verifica se a tabela alvo existe
            tb_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (target_tb,)).fetchone()
            if not tb_exists: continue
            
            # Executa o JOIN
            join_query = f"""
                SELECT t.* FROM {target_tb} t
                JOIN {rl_table} r ON t.{key_column} = r.{key_column}
                WHERE r.CO_PROCEDIMENTO = ?
            """
            
            joined_rows = conn.execute(join_query, (codigo,)).fetchall()
            if joined_rows:
                table_title = target_suffix.replace('_', ' ').title()
                header = list(dict(joined_rows[0]).keys())
                rows = [list(dict(r).values()) for r in joined_rows]
                
                related_data[table_title] = {
                    'header': header,
                    'rows': rows
                }
    except Exception as e:
        logging.error(f"Erro processando dados relacionais: {e}")

    sorted_keys = sorted([k for k in related_data.keys() if k != 'Ocupacao'])
    if 'Ocupacao' in related_data:
        sorted_keys.append('Ocupacao')
    ordered_related_data = {k: related_data[k] for k in sorted_keys}

    return render_template('procedimento_detail.html', proc=proc_principal, related_data=ordered_related_data, descricao=descricao)

@app.route('/contato')
def contato():
    return render_template('contato.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
