import sqlite3
import pandas as pd
import logging

FIELD_LABELS = {
    'NO_PROCEDIMENTO': 'Nome do Procedimento',
    'VL_SA': 'Valor Ambulatorial (SA)',
    'VL_H': 'Valor Hospitalar (H)',
    'TP_COMPLEXIDADE': 'Complexidade',
    'TP_SEXO': 'Sexo Permitido',
    'QT_MAXIMA_EXECUCAO': 'Qtd. Máxima de Execução',
    'QT_DIAS_PERMANENCIA': 'Dias de Permanência',
    'VL_IDADE_MINIMA': 'Idade Mínima',
    'VL_IDADE_MAXIMA': 'Idade Máxima',
    'CO_FINANCIAMENTO': 'Financiamento',
    'CO_RUBRICA': 'Rúbrica Orçamentária'
}

MONITORED_COLUMNS = list(FIELD_LABELS.keys())

def init_history_table(conn):
    """Garante a existência da tabela e índices de histórico de alterações."""
    sql = """
    CREATE TABLE IF NOT EXISTS tb_historico_alteracoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        co_procedimento TEXT NOT NULL,
        no_procedimento TEXT,
        competencia_de TEXT NOT NULL,
        competencia_para TEXT NOT NULL,
        tp_alteracao TEXT NOT NULL,
        campo_alterado TEXT,
        nome_campo TEXT,
        valor_anterior TEXT,
        valor_novo TEXT,
        dt_registro DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_hist_proc ON tb_historico_alteracoes(co_procedimento);
    CREATE INDEX IF NOT EXISTS idx_hist_comp ON tb_historico_alteracoes(competencia_para);
    CREATE INDEX IF NOT EXISTS idx_hist_tipo ON tb_historico_alteracoes(tp_alteracao);
    """
    conn.executescript(sql)
    conn.commit()

def format_val(val):
    if pd.isna(val) or val is None:
        return ""
    if isinstance(val, float):
        # format monetary or float neatly
        return f"{val:.2f}"
    return str(val).strip()

def compute_diffs_between_dbs(conn_old, conn_new):
    """
    Compara a tabela tb_procedimento de conn_old com conn_new e retorna uma lista de dicionários com os deltas.
    """
    # Obter competência antiga
    cur_old = conn_old.cursor()
    row_old = cur_old.execute("SELECT DT_COMPETENCIA FROM tb_procedimento LIMIT 1").fetchone()
    comp_old = str(row_old[0]) if row_old and row_old[0] else 'ANTERIOR'

    # Obter competência nova
    cur_new = conn_new.cursor()
    row_new = cur_new.execute("SELECT DT_COMPETENCIA FROM tb_procedimento LIMIT 1").fetchone()
    comp_new = str(row_new[0]) if row_new and row_new[0] else 'ATUAL'

    if comp_old == comp_new:
        logging.info(f"Mesma competência ({comp_old}), sem alterações a calcular.")
        return []

    logging.info(f"Calculando diferenças entre competência {comp_old} ➔ {comp_new}...")

    df_old = pd.read_sql_query("SELECT * FROM tb_procedimento", conn_old)
    df_new = pd.read_sql_query("SELECT * FROM tb_procedimento", conn_new)

    # Garantir colunas monitoradas
    for col in MONITORED_COLUMNS:
        if col not in df_old.columns: df_old[col] = None
        if col not in df_new.columns: df_new[col] = None

    df_old_map = df_old.set_index('CO_PROCEDIMENTO')
    df_new_map = df_new.set_index('CO_PROCEDIMENTO')

    old_codes = set(df_old_map.index)
    new_codes = set(df_new_map.index)

    added_codes = new_codes - old_codes
    removed_codes = old_codes - new_codes
    common_codes = old_codes & new_codes

    diffs = []

    # 1. Novidades (INCLUSAO)
    for code in added_codes:
        row = df_new_map.loc[code]
        no_proc = str(row['NO_PROCEDIMENTO']) if pd.notna(row['NO_PROCEDIMENTO']) else ""
        diffs.append({
            'co_procedimento': str(code),
            'no_procedimento': no_proc,
            'competencia_de': comp_old,
            'competencia_para': comp_new,
            'tp_alteracao': 'INCLUSAO',
            'campo_alterado': 'PROCEDIMENTO',
            'nome_campo': 'Novo Procedimento',
            'valor_anterior': None,
            'valor_novo': 'Incluído na tabela'
        })

    # 2. Exclusões (EXCLUSAO)
    for code in removed_codes:
        row = df_old_map.loc[code]
        no_proc = str(row['NO_PROCEDIMENTO']) if pd.notna(row['NO_PROCEDIMENTO']) else ""
        diffs.append({
            'co_procedimento': str(code),
            'no_procedimento': no_proc,
            'competencia_de': comp_old,
            'competencia_para': comp_new,
            'tp_alteracao': 'EXCLUSAO',
            'campo_alterado': 'PROCEDIMENTO',
            'nome_campo': 'Procedimento Descontinuado',
            'valor_anterior': 'Ativo anteriormente',
            'valor_novo': 'Removido da tabela'
        })

    # 3. Alterações em Procedimentos Comuns
    for code in common_codes:
        row_o = df_old_map.loc[code]
        row_n = df_new_map.loc[code]
        no_proc = str(row_n['NO_PROCEDIMENTO']) if pd.notna(row_n['NO_PROCEDIMENTO']) else str(row_o['NO_PROCEDIMENTO'])

        for col in MONITORED_COLUMNS:
            v_o = row_o[col]
            v_n = row_n[col]

            v_o_str = format_val(v_o)
            v_n_str = format_val(v_n)

            if v_o_str != v_n_str:
                if col in ['VL_SA', 'VL_H']:
                    tp = 'VALOR'
                elif col == 'NO_PROCEDIMENTO':
                    tp = 'NOME'
                else:
                    tp = 'ATRIBUTO'

                diffs.append({
                    'co_procedimento': str(code),
                    'no_procedimento': no_proc,
                    'competencia_de': comp_old,
                    'competencia_para': comp_new,
                    'tp_alteracao': tp,
                    'campo_alterado': col,
                    'nome_campo': FIELD_LABELS.get(col, col),
                    'valor_anterior': v_o_str if v_o_str else '(vazio)',
                    'valor_novo': v_n_str if v_n_str else '(vazio)'
                })

    logging.info(f"Total de {len(diffs)} deltas gerados entre {comp_old} e {comp_new}.")
    return diffs

def insert_diffs(conn, diffs):
    """Insere a lista de deltas na tabela tb_historico_alteracoes."""
    if not diffs:
        return
    init_history_table(conn)
    sql = """
    INSERT INTO tb_historico_alteracoes 
    (co_procedimento, no_procedimento, competencia_de, competencia_para, tp_alteracao, campo_alterado, nome_campo, valor_anterior, valor_novo)
    VALUES (:co_procedimento, :no_procedimento, :competencia_de, :competencia_para, :tp_alteracao, :campo_alterado, :nome_campo, :valor_anterior, :valor_novo)
    """
    conn.executemany(sql, diffs)
    conn.commit()

def copy_existing_history(conn_from, conn_to):
    """Copia registros de tb_historico_alteracoes de conn_from para conn_to se existirem."""
    init_history_table(conn_to)
    try:
        cur_from = conn_from.cursor()
        rows = cur_from.execute("SELECT co_procedimento, no_procedimento, competencia_de, competencia_para, tp_alteracao, campo_alterado, nome_campo, valor_anterior, valor_novo, dt_registro FROM tb_historico_alteracoes").fetchall()
        if rows:
            cur_to = conn_to.cursor()
            cur_to.executemany("""
                INSERT INTO tb_historico_alteracoes 
                (co_procedimento, no_procedimento, competencia_de, competencia_para, tp_alteracao, campo_alterado, nome_campo, valor_anterior, valor_novo, dt_registro)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn_to.commit()
            logging.info(f"Copiados {len(rows)} registros de histórico anteriores.")
    except Exception as e:
        logging.warning(f"Nenhum histórico anterior para copiar: {e}")
