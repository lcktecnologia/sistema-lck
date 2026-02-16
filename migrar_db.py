import sqlite3
import os
from datetime import datetime

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.db")

def conectar():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)

def column_exists(conn, table: str, column: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(c["name"] == column for c in cols)

def add_col(conn, table, col, typ):
    if table_exists(conn, table) and not column_exists(conn, table, col):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        print(f"[OK] Adicionada coluna {table}.{col}")

def main():
    if not os.path.exists(DATABASE):
        print("ERRO: database.db não existe nessa pasta. Confere se o arquivo está junto do app.py")
        return

    conn = conectar()

    # garantir tabelas (se faltar alguma)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        telefone TEXT,
        cpf TEXT,
        endereco TEXT,
        email TEXT
    )""")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS ordens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero_os TEXT UNIQUE,
        codigo_cliente TEXT,
        cliente_id INTEGER,
        status TEXT,
        defeito TEXT,

        equipamento_tipo TEXT,
        equip_marca TEXT,
        equip_modelo TEXT,
        imei TEXT,
        serial TEXT,

        equipamento_dados_json TEXT,
        relato_cliente TEXT,
        diagnostico_tecnico TEXT,
        servico_realizado TEXT,
        observacoes TEXT,

        valor_orcado REAL DEFAULT 0,
        valor_pago REAL DEFAULT 0,
        data_pagamento TEXT,

        criado_em TEXT,
        atualizado_em TEXT,

        encerrada INTEGER DEFAULT 0,
        encerrada_em TEXT
    )""")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS os_historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        os_id INTEGER NOT NULL,
        data_hora TEXT NOT NULL,
        usuario TEXT NOT NULL,
        evento TEXT NOT NULL,
        descricao TEXT,
        ocultar_cliente INTEGER DEFAULT 0
    )""")

    # MIGRAÇÕES IMPORTANTES
    add_col(conn, "ordens", "cliente_id", "INTEGER")
    add_col(conn, "ordens", "codigo_cliente", "TEXT")
    add_col(conn, "ordens", "equipamento_tipo", "TEXT")
    add_col(conn, "ordens", "equip_marca", "TEXT")
    add_col(conn, "ordens", "equip_modelo", "TEXT")
    add_col(conn, "ordens", "imei", "TEXT")
    add_col(conn, "ordens", "serial", "TEXT")
    add_col(conn, "ordens", "equipamento_dados_json", "TEXT")
    add_col(conn, "ordens", "relato_cliente", "TEXT")
    add_col(conn, "ordens", "diagnostico_tecnico", "TEXT")
    add_col(conn, "ordens", "servico_realizado", "TEXT")
    add_col(conn, "ordens", "observacoes", "TEXT")
    add_col(conn, "ordens", "valor_orcado", "REAL DEFAULT 0")
    add_col(conn, "ordens", "valor_pago", "REAL DEFAULT 0")
    add_col(conn, "ordens", "data_pagamento", "TEXT")
    add_col(conn, "ordens", "criado_em", "TEXT")
    add_col(conn, "ordens", "atualizado_em", "TEXT")
    add_col(conn, "ordens", "encerrada", "INTEGER DEFAULT 0")
    add_col(conn, "ordens", "encerrada_em", "TEXT")

    add_col(conn, "clientes", "cpf", "TEXT")
    add_col(conn, "clientes", "endereco", "TEXT")
    add_col(conn, "clientes", "email", "TEXT")

    # preencher datas em OS antigas
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE ordens SET criado_em=COALESCE(criado_em, ?)", (now,))
    conn.execute("UPDATE ordens SET atualizado_em=COALESCE(atualizado_em, ?)", (now,))

    conn.commit()
    conn.close()
    print("\n✅ Migração concluída. Agora rode: py app.py")

if __name__ == "__main__":
    main()
