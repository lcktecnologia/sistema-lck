import sqlite3

DB = "database.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS usuarios")
cur.execute("""
CREATE TABLE usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL
)
""")

cur.execute("INSERT INTO usuarios(usuario, senha) VALUES (?, ?)", ("lucas", "123"))
cur.execute("INSERT INTO usuarios(usuario, senha) VALUES (?, ?)", ("tiago", "123"))
cur.execute("INSERT INTO usuarios(usuario, senha) VALUES (?, ?)", ("natan", "123"))

conn.commit()
conn.close()

print("OK! USUÁRIOS CRIADOS: lucas, tiago, natan (senha 123)")
