import os
import json
import random
import string
from functools import wraps
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, abort
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "troque-essa-chave-por-algo-seu-123")

# =========================
# CONFIG
# =========================
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
SITE_CONSULTA = os.environ.get("SITE_CONSULTA", "https://sistema-lck.onrender.com/").strip()

# =========================
# DB (Postgres / Neon)
# =========================
def get_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada no Render.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ensure_tables():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        role TEXT DEFAULT 'user'
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS os (
        id SERIAL PRIMARY KEY,
        data_entrada TEXT,
        status TEXT DEFAULT 'aberta',

        cliente_nome TEXT,
        cliente_fone TEXT,
        cliente_cpf TEXT,
        cliente_endereco TEXT,
        cliente_email TEXT,

        tipo TEXT,
        equipamento TEXT,

        checklist_json TEXT,
        relato_cliente TEXT,
        diagnostico_tecnico TEXT,

        valor_orcado NUMERIC DEFAULT 0,
        valor_pago NUMERIC DEFAULT 0,
        data_pagamento TEXT,

        codigo_consulta TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS os_historico (
        id SERIAL PRIMARY KEY,
        os_id INTEGER NOT NULL,
        data TEXT,
        acao TEXT,
        obs TEXT,
        visivel_cliente INTEGER DEFAULT 1,

        valor_orcado NUMERIC DEFAULT NULL,
        valor_pago NUMERIC DEFAULT NULL,
        data_pagamento TEXT DEFAULT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS devedores (
        id SERIAL PRIMARY KEY,
        criado_em TEXT,
        cliente_nome TEXT,
        cliente_fone TEXT,
        referencia TEXT,
        valor NUMERIC DEFAULT 0,
        obs TEXT,
        status TEXT DEFAULT 'em aberto',
        pago_em TEXT
    );
    """)

    def upsert_user(usuario, senha, role):
        cur.execute("""
            INSERT INTO usuarios (usuario, senha, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (usuario)
            DO UPDATE SET senha = EXCLUDED.senha, role = EXCLUDED.role;
        """, (usuario, senha, role))

    # usuários fixos
    upsert_user("Lucas", "0904", "admin")
    upsert_user("Carol", "2858", "admin")
    upsert_user("Natan", "0000", "user")
    upsert_user("Tiago", "1234", "user")

    conn.commit()
    conn.close()

@app.before_request
def startup():
    # roda 1x por instância
    if not getattr(app, "_db_ready", False):
        ensure_tables()
        app._db_ready = True
        print("✅ DB Postgres/Neon pronto.")

# =========================
# Helpers / Permissões
# =========================
def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Ação permitida apenas para administradores.", "err")
            return redirect(url_for("painel"))
        return fn(*args, **kwargs)
    return wrapper

def parse_money(v):
    v = (v or "").strip().replace(".", "").replace(",", ".")
    try:
        return float(v) if v else 0.0
    except Exception:
        return 0.0

def gen_codigo_consulta(conn) -> str:
    cur = conn.cursor()
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        cur.execute("SELECT 1 FROM os WHERE codigo_consulta = %s", (code,))
        if not cur.fetchone():
            return code

STATUS_LABEL = {
    "aberta": "Aberta",
    "aguardando orçamento": "Aguardando orçamento",
    "aguardando aprovação": "Aguardando aprovação",
    "em execução": "Serviço em execução",
    "fechada": "Finalizado",
    "sem conserto": "Sem conserto",
}
STATUS_CLASS = {
    "aberta": "st-aberta",
    "aguardando orçamento": "st-orc",
    "aguardando aprovação": "st-aprov",
    "em execução": "st-exec",
    "fechada": "st-fechada",
    "sem conserto": "st-sem",
}

CHECKLIST_LABELS = {
    "ck_cel_tela_estado": "Estado da tela",
    "ck_cel_tela_quebrada": "Tela quebrada",
    "ck_cel_touch": "Touch funcionando",
    "ck_cel_display": "Imagem/Display",
    "ck_cel_liga": "Aparelho liga",
    "ck_cel_carrega": "Carrega",
    "ck_cel_bateria_pct": "Percentual aproximado de bateria",
    "ck_cel_power": "Botão Power",
    "ck_cel_volume": "Botões volume",
    "ck_cel_vibracao": "Vibração",
    "ck_cel_wifi": "Wi-Fi",
    "ck_cel_bluetooth": "Bluetooth",
    "ck_cel_chip": "Chip (SIM)",
    "ck_cel_gaveta": "Gaveta do chip",
    "ck_cel_imei1": "IMEI 1",
    "ck_cel_imei2": "IMEI 2",
    "ck_cel_cam_frontal": "Câmera frontal",
    "ck_cel_cam_traseira": "Câmera traseira",
    "ck_cel_flash": "Flash",
    "ck_cel_audio": "Áudio / alto-falante",
    "ck_cel_microfone": "Microfone",
    "ck_cel_conector": "Conector de carga",
    "ck_cel_agua": "Molhou / oxidou",
    "ck_cel_biometria": "Biometria / Face ID",
    "ck_cel_proximidade": "Sensor de proximidade",
    "ck_cel_conta": "Conta Google/iCloud vinculada",
    "ck_cel_senha": "Senha / padrão",
    "ck_cel_carcaca": "Carcaça / laterais",
    "ck_cel_tampa": "Tampa traseira",
    "ck_cel_pelicula_capa": "Película / capa",
    "ck_cel_sd": "Cartão de memória",
    "ck_cel_acessorios": "Acessórios recebidos",
    "ck_cel_obs_receb": "Observações do recebimento",

    "ck_pc_fonte": "Fonte",
    "ck_pc_bateria": "Bateria (notebook)",
    "ck_pc_hdssd": "HD/SSD",
    "ck_pc_teclado": "Estado do teclado",
    "ck_pc_tela": "Estado da tela (notebook)",
    "ck_pc_senha": "Senha (Windows/BIOS)",
    "ck_pc_acessorios": "Acessórios recebidos",

    "ck_tv_polegadas": "Polegadas",
    "ck_tv_controle": "Controle",
    "ck_tv_fonte": "Cabo / fonte",
    "ck_tv_tela_trincada": "Tela trincada",
    "ck_tv_base": "Base / suporte",
    "ck_tv_cabos": "Cabos adicionais",

    "ck_vg_controles": "Controles",
    "ck_vg_cabos": "Cabos",
    "ck_vg_leitor": "Leitor de disco",
    "ck_vg_conta": "Conta / senha",

    "ck_outro_acessorios": "Acessórios recebidos",
    "ck_outro_estado": "Estado externo",
    "ck_outro_detalhes": "Detalhes / observações",
}

@app.context_processor
def inject_helpers():
    def pad_os(n: int) -> str:
        try:
            return str(int(n)).zfill(4)
        except Exception:
            return "0000"

    return dict(
        pad_os=pad_os,
        STATUS_LABEL=STATUS_LABEL,
        STATUS_CLASS=STATUS_CLASS,
        CHECKLIST_LABELS=CHECKLIST_LABELS,
        site_consulta=SITE_CONSULTA
    )

# =========================
# Rotas públicas
# =========================
@app.get("/")
def index():
    return render_template("index.html")

@app.get("/inicio")
def inicio():
    return redirect(url_for("index"))

@app.get("/consultar")
def consultar():
    return render_template("consultar.html")

@app.post("/consultar")
def consultar_post():
    os_id_raw = (request.form.get("os_id", "") or "").strip()
    codigo = (request.form.get("codigo", "") or "").strip().upper()

    if not os_id_raw.isdigit():
        return render_template("consultar.html", erro="Informe o número da OS (apenas números).")

    os_id = int(os_id_raw)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM os WHERE id = %s", (os_id,))
    row = cur.fetchone()

    if not row:
        conn.close()
        return render_template("consultar.html", erro="OS não encontrada.")

    if str(row.get("codigo_consulta") or "").upper() != str(codigo).upper():
        conn.close()
        return render_template("consultar.html", erro="Código inválido.")

    cur.execute("""
        SELECT * FROM os_historico
        WHERE os_id = %s AND visivel_cliente = 1
        ORDER BY id DESC
    """, (os_id,))
    hist = cur.fetchall()

    conn.close()
    return render_template("consultar.html", resultado=row, historico=hist)

# =========================
# Auth
# =========================
@app.get("/login")
def login():
    return render_template("login.html")

@app.post("/login")
def login_post():
    usuario = request.form.get("usuario", "").strip()
    senha = request.form.get("senha", "").strip()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM usuarios WHERE usuario = %s", (usuario,))
    u = cur.fetchone()
    conn.close()

    if not u or str(u["senha"]) != str(senha):
        flash("Usuário ou senha inválidos.", "err")
        return redirect(url_for("login"))

    session["user_id"] = u["id"]
    session["usuario"] = u["usuario"]
    session["role"] = u.get("role", "user")
    return redirect(url_for("painel"))

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# =========================
# Painel
# =========================
@app.get("/painel")
@login_required
def painel():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, data_entrada, status, cliente_nome, cliente_fone, tipo, equipamento, codigo_consulta
        FROM os
        WHERE status IN ('aberta','aguardando orçamento','aguardando aprovação','em execução')
        ORDER BY id DESC
        LIMIT 80
    """)
    abertas = cur.fetchall()
    conn.close()
    return render_template("painel.html", abertas=abertas)

@app.get("/os/finalizadas")
@login_required
def os_finalizadas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM os
        WHERE status IN ('fechada','sem conserto')
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return render_template("os_listar.html", rows=rows, grupo="finalizadas")

# =========================
# Devedores
# =========================
@app.get("/devedores")
@login_required
def devedores():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM devedores
        ORDER BY CASE WHEN status='em aberto' THEN 0 ELSE 1 END, id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return render_template("devedores.html", rows=rows)

@app.get("/devedores/novo")
@login_required
def devedores_novo():
    return render_template("devedor_novo.html", prefill=None, from_os_id=None)

@app.post("/devedores/novo")
@login_required
def devedores_novo_post():
    cliente_nome = (request.form.get("cliente_nome") or "").strip()
    cliente_fone = (request.form.get("cliente_fone") or "").strip()
    referencia = (request.form.get("referencia") or "").strip()
    valor = parse_money(request.form.get("valor"))
    obs = (request.form.get("obs") or "").strip()

    if not cliente_nome:
        flash("Informe o nome do cliente.", "err")
        return redirect(url_for("devedores_novo"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO devedores (criado_em, cliente_nome, cliente_fone, referencia, valor, obs, status, pago_em)
        VALUES (%s, %s, %s, %s, %s, %s, 'em aberto', NULL)
    """, (now_str(), cliente_nome, cliente_fone, referencia, valor, obs))
    conn.commit()
    conn.close()

    flash("Devedor cadastrado.", "ok")
    return redirect(url_for("devedores"))

@app.post("/devedores/<int:dev_id>/pagar")
@login_required
def devedor_marcar_pago(dev_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE devedores SET status='pago', pago_em=%s WHERE id=%s", (now_str(), dev_id))
    conn.commit()
    conn.close()
    flash("Marcado como pago.", "ok")
    return redirect(url_for("devedores"))

@app.post("/devedores/<int:dev_id>/reabrir")
@login_required
def devedor_reabrir(dev_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE devedores SET status='em aberto', pago_em=NULL WHERE id=%s", (dev_id,))
    conn.commit()
    conn.close()
    flash("Devedor reaberto.", "ok")
    return redirect(url_for("devedores"))

@app.post("/devedores/<int:dev_id>/excluir")
@login_required
@admin_required
def devedor_excluir(dev_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM devedores WHERE id=%s", (dev_id,))
    conn.commit()
    conn.close()
    flash("Devedor excluído.", "ok")
    return redirect(url_for("devedores"))

# botão dentro da OS: criar devedor preenchido
@app.get("/os/<int:os_id>/devedor")
@login_required
def os_devedor_form(os_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM os WHERE id=%s", (os_id,))
    o = cur.fetchone()
    conn.close()

    if not o:
        abort(404)

    vo = float(o.get("valor_orcado") or 0)
    vp = float(o.get("valor_pago") or 0)
    sugerido = vo - vp
    if sugerido < 0:
        sugerido = 0

    prefill = {
        "cliente_nome": o.get("cliente_nome") or "",
        "cliente_fone": o.get("cliente_fone") or "",
        "referencia": f"OS #{str(int(o['id'])).zfill(4)}",
        "valor": f"{sugerido:.2f}".replace(".", ","),
        "obs": ""
    }
    return render_template("devedor_novo.html", prefill=prefill, from_os_id=os_id)

@app.post("/os/<int:os_id>/devedor")
@login_required
def os_devedor_post(os_id):
    cliente_nome = (request.form.get("cliente_nome") or "").strip()
    cliente_fone = (request.form.get("cliente_fone") or "").strip()
    referencia = (request.form.get("referencia") or "").strip()
    valor = parse_money(request.form.get("valor"))
    obs = (request.form.get("obs") or "").strip()

    if not cliente_nome:
        flash("Informe o nome do cliente.", "err")
        return redirect(url_for("os_devedor_form", os_id=os_id))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO devedores (criado_em, cliente_nome, cliente_fone, referencia, valor, obs, status, pago_em)
        VALUES (%s, %s, %s, %s, %s, %s, 'em aberto', NULL)
    """, (now_str(), cliente_nome, cliente_fone, referencia, valor, obs))

    cur.execute("""
        INSERT INTO os_historico (os_id, data, acao, obs, visivel_cliente)
        VALUES (%s, %s, %s, %s, 0)
    """, (os_id, now_str(), "Devedor registrado",
          f"Devedor criado: {cliente_nome} • R$ {valor:.2f} • {referencia}"))

    conn.commit()
    conn.close()

    flash("Devedor adicionado a partir da OS.", "ok")
    return redirect(url_for("os_detalhe", os_id=os_id))

# =========================
# Criar OS
# =========================
@app.get("/os/nova")
@login_required
def os_nova():
    return render_template("nova_os.html")

@app.post("/os/nova")
@login_required
def os_nova_post():
    data_entrada = now_str()

    cliente_nome = request.form.get("cliente_nome", "").strip()
    cliente_fone = request.form.get("cliente_fone", "").strip()
    cliente_cpf = request.form.get("cliente_cpf", "").strip()
    cliente_endereco = request.form.get("cliente_endereco", "").strip()
    cliente_email = request.form.get("cliente_email", "").strip()

    tipo = request.form.get("tipo", "").strip()
    equipamento = request.form.get("equipamento", "").strip()

    relato_cliente = request.form.get("relato_cliente", "").strip()
    diagnostico_tecnico = request.form.get("diagnostico_tecnico", "").strip()

    valor_orcado = parse_money(request.form.get("valor_orcado"))
    valor_pago = parse_money(request.form.get("valor_pago"))
    data_pagamento = request.form.get("data_pagamento", "").strip()

    checklist = {}
    for k, v in request.form.items():
        if k.startswith("ck_") and (v or "").strip():
            checklist[k] = v.strip()

    conn = get_db()
    cur = conn.cursor()

    codigo = gen_codigo_consulta(conn)

    cur.execute("""
        INSERT INTO os (
            data_entrada, status,
            cliente_nome, cliente_fone, cliente_cpf, cliente_endereco, cliente_email,
            tipo, equipamento,
            checklist_json, relato_cliente, diagnostico_tecnico,
            valor_orcado, valor_pago, data_pagamento,
            codigo_consulta
        )
        VALUES (
            %s, 'aberta',
            %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s
        )
        RETURNING id
    """, (
        data_entrada,
        cliente_nome, cliente_fone, cliente_cpf, cliente_endereco, cliente_email,
        tipo, equipamento,
        json.dumps(checklist, ensure_ascii=False),
        relato_cliente, diagnostico_tecnico,
        valor_orcado, valor_pago, data_pagamento,
        codigo
    ))

    os_id = cur.fetchone()["id"]

    cur.execute("""
        INSERT INTO os_historico (os_id, data, acao, obs, visivel_cliente, valor_orcado, valor_pago, data_pagamento)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        os_id, now_str(), "OS criada", "Entrada registrada no sistema.", 1,
        (valor_orcado if request.form.get("valor_orcado") else None),
        (valor_pago if request.form.get("valor_pago") else None),
        (data_pagamento if request.form.get("data_pagamento") else None)
    ))

    conn.commit()
    conn.close()

    return redirect(url_for("os_detalhe", os_id=os_id))

# =========================
# Detalhe / Atualizações
# =========================
@app.get("/os/<int:os_id>")
@login_required
def os_detalhe(os_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM os WHERE id = %s", (os_id,))
    os_row = cur.fetchone()
    if not os_row:
        conn.close()
        abort(404)

    cur.execute("""
        SELECT * FROM os_historico
        WHERE os_id = %s
        ORDER BY id DESC
    """, (os_id,))
    hist = cur.fetchall()

    conn.close()

    checklist = {}
    try:
        checklist = json.loads(os_row.get("checklist_json") or "{}")
    except Exception:
        checklist = {}

    return render_template("os_detalhe.html", os_row=os_row, historico=hist, checklist=checklist)

@app.post("/os/<int:os_id>/historico")
@login_required
def os_add_historico(os_id):
    acao = (request.form.get("acao") or "Observação").strip()
    obs = (request.form.get("obs") or "").strip()
    visivel_cliente = 1 if request.form.get("visivel_cliente") == "1" else 0

    novo_status = (request.form.get("novo_status") or "").strip().lower()
    valor_orcado = parse_money(request.form.get("valor_orcado"))
    valor_pago = parse_money(request.form.get("valor_pago"))
    data_pagamento = (request.form.get("data_pagamento") or "").strip()

    allowed_status = set(STATUS_LABEL.keys())
    if novo_status and novo_status not in allowed_status:
        novo_status = ""

    conn = get_db()
    cur = conn.cursor()

    # atualiza OS (somente campos enviados)
    fields = []
    values = []

    if novo_status:
        fields.append("status=%s")
        values.append(novo_status)

    if request.form.get("valor_orcado") not in (None, ""):
        fields.append("valor_orcado=%s")
        values.append(valor_orcado)

    if request.form.get("valor_pago") not in (None, ""):
        fields.append("valor_pago=%s")
        values.append(valor_pago)

    if request.form.get("data_pagamento") not in (None, ""):
        fields.append("data_pagamento=%s")
        values.append(data_pagamento)

    if fields:
        values.append(os_id)
        cur.execute(f"UPDATE os SET {', '.join(fields)} WHERE id=%s", tuple(values))

    # snapshot pós update
    cur.execute("SELECT valor_orcado, valor_pago, data_pagamento FROM os WHERE id=%s", (os_id,))
    after = cur.fetchone()
    if not after:
        conn.close()
        abort(404)

    cur.execute("""
        INSERT INTO os_historico (os_id, data, acao, obs, visivel_cliente, valor_orcado, valor_pago, data_pagamento)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        os_id, now_str(), acao, obs, visivel_cliente,
        after.get("valor_orcado"),
        after.get("valor_pago"),
        after.get("data_pagamento")
    ))

    conn.commit()
    conn.close()

    flash("Atualização registrada.", "ok")
    return redirect(url_for("os_detalhe", os_id=os_id))

# =========================
# IMPRESSÃO (isso resolve seu BuildError)
# =========================

# ✅ ESTE É O ENDPOINT QUE O SEU TEMPLATE ESTÁ CHAMANDO
@app.get("/os/<int:os_id>/comprovante")
@login_required
def os_comprovante(os_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM os WHERE id=%s", (os_id,))
    os_row = cur.fetchone()
    conn.close()

    if not os_row:
        abort(404)

    # seu template usa variável "os" e "site_consulta"
    return render_template("comprovante.html", os=os_row, site_consulta=SITE_CONSULTA)

# Imprimir OS completa (se seu botão existir no template)
@app.get("/os/<int:os_id>/imprimir")
@login_required
def os_imprimir(os_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM os WHERE id=%s", (os_id,))
    os_row = cur.fetchone()
    if not os_row:
        conn.close()
        abort(404)

    cur.execute("SELECT * FROM os_historico WHERE os_id=%s ORDER BY id DESC", (os_id,))
    hist = cur.fetchall()
    conn.close()

    checklist = {}
    try:
        checklist = json.loads(os_row.get("checklist_json") or "{}")
    except Exception:
        checklist = {}

    # ajuste: aqui eu chamei de os_row/checklist/historico igual ao detalhe
    return render_template("os_imprimir.html", os_row=os_row, checklist=checklist, historico=hist, site_consulta=SITE_CONSULTA)

# =========================
# Run local
# =========================
if __name__ == "__main__":
    app.run(debug=True) 