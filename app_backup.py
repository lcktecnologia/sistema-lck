# app.py
from flask import Flask, render_template, request, redirect, session, url_for, flash, abort
import sqlite3
import os
import secrets
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "lck-dev-key-trocar-depois")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")


def agora_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def conectar():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(BASE_DIR, exist_ok=True)
    conn = conectar()
    cur = conn.cursor()

    # usuários
    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'tecnico'
    )
    """)

    # ordem de serviço
    cur.execute("""
    CREATE TABLE IF NOT EXISTS os (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT UNIQUE NOT NULL,
        codigo TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        atualizado_em TEXT NOT NULL,

        status TEXT NOT NULL DEFAULT 'ABERTA',

        -- dados cliente
        cliente_nome TEXT,
        cliente_telefone TEXT,
        cliente_cpf TEXT,
        cliente_email TEXT,
        cliente_endereco TEXT,

        -- dados equipamento
        equipamento_tipo TEXT,
        equipamento_marca TEXT,
        equipamento_modelo TEXT,
        equipamento_imei TEXT,
        equipamento_serial TEXT,

        -- relato inicial
        defeito TEXT,

        -- valores
        valor_orcado REAL DEFAULT 0,
        valor_pago REAL DEFAULT 0,
        data_pagamento TEXT
    )
    """)

    # histórico interno (com flag se o cliente pode ver)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        os_id INTEGER NOT NULL,
        data_hora TEXT NOT NULL,
        evento TEXT NOT NULL,
        descricao TEXT,
        usuario TEXT,
        visivel_cliente INTEGER DEFAULT 1,
        FOREIGN KEY(os_id) REFERENCES os(id)
    )
    """)

    # cria admin padrão se não existir
    u = cur.execute("SELECT 1 FROM usuarios WHERE usuario='lucas'").fetchone()
    if not u:
        # senha padrão: 1234 (troque depois)
        cur.execute("INSERT INTO usuarios (usuario, senha, role) VALUES (?,?,?)",
                    ("lucas", "1234", "admin"))

    conn.commit()
    conn.close()

    print(f"✅ DB em uso: {DATABASE}")


def login_required():
    if "usuario" not in session:
        return False
    return True


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()
        senha = (request.form.get("senha") or "").strip()

        conn = conectar()
        u = conn.execute("SELECT * FROM usuarios WHERE usuario=?", (usuario,)).fetchone()
        conn.close()

        if not u or u["senha"] != senha:
            flash("Usuário ou senha inválidos.", "error")
            return redirect(url_for("login"))

        session["usuario"] = u["usuario"]
        session["role"] = u["role"]
        return redirect(url_for("painel"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/painel")
def painel():
    if not login_required():
        return redirect(url_for("login"))

    conn = conectar()
    abertas = conn.execute("""
        SELECT id, numero, codigo, status, cliente_nome, cliente_telefone,
               equipamento_tipo, equipamento_marca, equipamento_modelo,
               atualizado_em, valor_orcado, valor_pago
        FROM os
        WHERE status NOT IN ('FINALIZADO (ENTREGUE)', 'CANCELADO')
        ORDER BY atualizado_em DESC
    """).fetchall()

    finalizadas = conn.execute("""
        SELECT id, numero, codigo, status, cliente_nome, cliente_telefone,
               equipamento_tipo, equipamento_marca, equipamento_modelo,
               atualizado_em, valor_orcado, valor_pago
        FROM os
        WHERE status IN ('FINALIZADO (ENTREGUE)', 'CANCELADO')
        ORDER BY atualizado_em DESC
        LIMIT 100
    """).fetchall()

    conn.close()

    return render_template(
        "painel.html",
        abertas=abertas,
        finalizadas=finalizadas
    )


def gerar_numero_os(conn):
    # OS-0001, OS-0002...
    row = conn.execute("SELECT COUNT(*) as c FROM os").fetchone()
    n = (row["c"] or 0) + 1
    return f"OS-{n:04d}"


def gerar_codigo():
    # 6 chars
    return secrets.token_hex(3).upper()


@app.route("/os/nova", methods=["GET", "POST"])
def os_nova():
    if not login_required():
        return redirect(url_for("login"))

    if request.method == "GET":
        # ✅ GARANTIDO que é o template certo:
        return render_template("nova_os.html")

    # POST (criar OS)
    cliente_nome = (request.form.get("cliente_nome") or "").strip()
    cliente_telefone = (request.form.get("cliente_telefone") or "").strip()
    cliente_cpf = (request.form.get("cliente_cpf") or "").strip()
    cliente_email = (request.form.get("cliente_email") or "").strip()
    cliente_endereco = (request.form.get("cliente_endereco") or "").strip()

    equipamento_tipo = (request.form.get("equipamento_tipo") or "").strip()
    equipamento_marca = (request.form.get("equipamento_marca") or "").strip()
    equipamento_modelo = (request.form.get("equipamento_modelo") or "").strip()
    equipamento_imei = (request.form.get("equipamento_imei") or "").strip()
    equipamento_serial = (request.form.get("equipamento_serial") or "").strip()

    defeito = (request.form.get("defeito") or "").strip()

    conn = conectar()
    numero = gerar_numero_os(conn)
    codigo = gerar_codigo()
    criado_em = agora_str()

    conn.execute("""
        INSERT INTO os (
            numero, codigo, criado_em, atualizado_em,
            status,
            cliente_nome, cliente_telefone, cliente_cpf, cliente_email, cliente_endereco,
            equipamento_tipo, equipamento_marca, equipamento_modelo, equipamento_imei, equipamento_serial,
            defeito
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        numero, codigo, criado_em, criado_em,
        "ABERTA",
        cliente_nome, cliente_telefone, cliente_cpf, cliente_email, cliente_endereco,
        equipamento_tipo, equipamento_marca, equipamento_modelo, equipamento_imei, equipamento_serial,
        defeito
    ))

    os_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

    # histórico inicial
    conn.execute("""
        INSERT INTO historico (os_id, data_hora, evento, descricao, usuario, visivel_cliente)
        VALUES (?,?,?,?,?,?)
    """, (os_id, criado_em, "ABERTA", "Entrada do equipamento / OS criada.", session.get("usuario"), 1))

    conn.commit()
    conn.close()

    flash(f"OS criada: {numero} | Código: {codigo}", "success")

    # ✅ NÃO imprime automático. Vai pro detalhe.
    return redirect(url_for("os_detalhe", os_id=os_id))


@app.route("/os/<int:os_id>")
def os_detalhe(os_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = conectar()
    os_row = conn.execute("SELECT * FROM os WHERE id=?", (os_id,)).fetchone()
    if not os_row:
        conn.close()
        abort(404)

    hist = conn.execute("""
        SELECT * FROM historico
        WHERE os_id=?
        ORDER BY id DESC
    """, (os_id,)).fetchall()

    conn.close()
    return render_template("os_detalhe.html", os_row=os_row, historico=hist)


@app.route("/os/<int:os_id>/comprovante")
def os_comprovante(os_id):
    # impressão separada
    if not login_required():
        return redirect(url_for("login"))

    conn = conectar()
    os_row = conn.execute("SELECT * FROM os WHERE id=?", (os_id,)).fetchone()
    if not os_row:
        conn.close()
        abort(404)

    hist = conn.execute("""
        SELECT * FROM historico
        WHERE os_id=?
        ORDER BY id ASC
    """, (os_id,)).fetchall()

    conn.close()
    return render_template("os_comprovante.html", os_row=os_row, historico=hist)


@app.route("/consultar", methods=["GET", "POST"])
def consultar():
    resultado = None
    if request.method == "POST":
        numero = (request.form.get("numero") or "").strip().upper()
        codigo = (request.form.get("codigo") or "").strip().upper()

        if numero and not numero.startswith("OS-"):
            # permite digitar só "0001" etc
            if numero.isdigit():
                numero = f"OS-{int(numero):04d}"

        conn = conectar()
        os_row = conn.execute(
            "SELECT * FROM os WHERE numero=? AND codigo=?",
            (numero, codigo)
        ).fetchone()

        if os_row:
            # cliente vê histórico filtrado (visivel_cliente=1)
            hist = conn.execute("""
                SELECT * FROM historico
                WHERE os_id=? AND visivel_cliente=1
                ORDER BY id DESC
                LIMIT 50
            """, (os_row["id"],)).fetchall()
            resultado = {"os": os_row, "hist": hist}

        conn.close()

    return render_template("consultar.html", resultado=resultado)


@app.errorhandler(404)
def pagina_nao_encontrada(e):
    return "<h2>Página não encontrada (404)</h2><p>Essa URL não existe no Flask.</p>", 404


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
