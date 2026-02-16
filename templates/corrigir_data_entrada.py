import sqlite3
from datetime import datetime

DB = "database.db"

def get_tables(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return [r[0] for r in cur.fetchall()]

def get_columns(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

def find_os_table(conn):
    # nomes comuns que seu projeto pode estar usando
    candidates = ["ordens_servico", "ordem_servico", "os", "ordens", "ordem", "chamados"]
    tables = get_tables(conn)

    for t in candidates:
        if t in tables:
            cols = get_columns(conn, t)
            # tem cara de tabela de OS
            if "status" in cols or "cliente" in cols or "equipamento" in cols:
                return t

    # fallback: tenta achar uma tabela que tenha "status" e "id"
    for t in tables:
        cols = get_columns(conn, t)
        if "id" in cols and "status" in cols:
            return t

    return None

conn = sqlite3.connect(DB)
cur = conn.cursor()

tabela_os = find_os_table(conn)
if not tabela_os:
    print("ERRO: Não consegui identificar a tabela de OS automaticamente.")
    print("Tabelas existentes:", get_tables(conn))
    conn.close()
    raise SystemExit(1)

cols = get_columns(conn, tabela_os)

if "data_entrada" not in cols:
    print(f"Adicionando coluna data_entrada na tabela: {tabela_os} ...")
    cur.execute(f"ALTER TABLE {tabela_os} ADD COLUMN data_entrada TEXT")
    conn.commit()
else:
    print(f"Coluna data_entrada já existe na tabela: {tabela_os}")

# preenche vazio nas OS antigas
agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
cur.execute(f"UPDATE {tabela_os} SET data_entrada = COALESCE(data_entrada, ?) ", (agora,))
conn.commit()

conn.close()
print("OK! Corrigido: data_entrada criada/preenchida.")
