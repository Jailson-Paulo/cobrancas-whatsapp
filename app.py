import os
import re
from datetime import date, datetime
from calendar import monthrange
from urllib.parse import quote

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, flash, redirect, render_template_string, request, url_for
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")

PIX_PADRAO = "06151758480"
VALOR_PADRAO = 25.00

HTML = r"""
<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cobranças WhatsApp</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Inter,Arial,sans-serif;background:#f4f7fb;color:#172033}
header{background:#102a43;color:#fff;padding:20px 4%;display:flex;justify-content:space-between;align-items:center;gap:15px}
header h1{margin:0;font-size:22px}main{max-width:1250px;margin:25px auto;padding:0 18px}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}.card{background:#fff;border-radius:14px;padding:16px;box-shadow:0 2px 12px #0000000d}.card b{font-size:22px;display:block;margin-top:5px}
form.box{background:#fff;padding:20px;border-radius:14px;margin:18px 0;box-shadow:0 2px 12px #0000000d}
.fields{display:grid;grid-template-columns:2fr 1.3fr 1fr 1.2fr 1.4fr auto;gap:10px;align-items:end}
label{font-size:12px;font-weight:700;display:block;margin-bottom:5px}input,textarea,button{font:inherit}input,textarea{width:100%;padding:11px;border:1px solid #d5dce5;border-radius:9px}
button,.btn{border:0;border-radius:9px;padding:10px 13px;cursor:pointer;text-decoration:none;display:inline-block;font-weight:700}.primary{background:#1677ff;color:white}.success{background:#16a36a;color:white}.warn{background:#e99b00;color:#fff}.muted{background:#e8edf3;color:#243447}.danger{background:#dc3545;color:#fff}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 2px 12px #0000000d}th,td{padding:13px;border-bottom:1px solid #edf0f4;text-align:left}th{background:#f8fafc;font-size:12px}.status{padding:5px 9px;border-radius:20px;font-size:12px;font-weight:700}.pago{background:#dff7ea;color:#087443}.pendente{background:#fff0d1;color:#875600}.actions{display:flex;gap:6px;flex-wrap:wrap}.mobile{display:none}.alert{padding:12px;border-radius:10px;margin:8px 0;background:#fff}.msg{background:#102a43;color:#fff;padding:15px;border-radius:12px;margin:15px 0}
.section-title{margin-top:28px}.small{font-size:12px;color:#637083}.group{margin:15px 0}
@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}.fields{grid-template-columns:1fr 1fr}.fields .wide{grid-column:1/-1}table{display:none}.mobile{display:block}.client{background:#fff;margin:10px 0;padding:15px;border-radius:14px;box-shadow:0 2px 10px #0000000b}.client-head{display:flex;justify-content:space-between;gap:10px}.actions{margin-top:12px}.actions .btn{flex:1;text-align:center}}
@media(max-width:500px){header{padding:16px}main{padding:0 12px}.grid{grid-template-columns:1fr 1fr}.fields{grid-template-columns:1fr}.fields .wide{grid-column:auto}.card b{font-size:18px}}
</style>
</head>
<body>
<header><h1>💬 Cobranças WhatsApp</h1><span>Pix: {{ pix }}</span></header>
<main>
<div class="grid">
{% for title,value in stats %}<div class="card"><span>{{ title }}</span><b>{{ value }}</b></div>{% endfor %}
</div>

<form class="box" method="post" action="{{ url_for('add_cliente') }}">
<h2>➕ Novo cliente</h2>
<div class="fields">
<div class="wide"><label>Nome</label><input name="nome" required></div>
<div><label>WhatsApp</label><input name="whatsapp" placeholder="5581999999999" required></div>
<div><label>Valor (R$)</label><input name="valor_plano" type="number" step="0.01" min="0" value="25.00" required></div>
<div><label>Vencimento</label><input name="data_vencimento" type="date" required></div>
<div><label>Chave Pix</label><input name="chave_pix" value="{{ pix }}"></div>
<div class="wide"><label>Detalhes</label><textarea name="detalhes_mac" rows="2" placeholder="Informações sobre o Mac, observações, configuração, etc."></textarea></div>
<div><label>Site</label><input name="site" type="url" placeholder="https://..."></div>
<div><label>Usuário criado em</label><input name="data_criacao_usuario" type="date"></div>
<button class="primary">Cadastrar</button>
</div>
</form>

<form class="box" method="post" action="{{ url_for('notificar_todos') }}">
<h2>📢 Notificar todos</h2>
<textarea name="mensagem" rows="3" placeholder="Digite a mensagem que será preparada para cada cliente..." required></textarea>
<br><br><button class="primary">Gerar links individuais</button>
</form>

{% if links %}
<div class="box"><h2>📲 Links gerados</h2>
{% for item in links %}<div class="alert"><b>{{ item.nome }}</b> — <a class="btn success" target="_blank" href="{{ item.link }}">Abrir WhatsApp</a></div>{% endfor %}
</div>
{% endif %}

<h2 class="section-title">🔔 Alertas de vencimento</h2>
{% for grupo in alertas %}
<div class="group"><b>{{ grupo.titulo }} ({{ grupo.clientes|length }})</b>
{% if grupo.clientes %}{% for c in grupo.clientes %}<div class="alert">{{ c.nome }} — {{ c.data_vencimento }} — R$ {{ "%.2f"|format(c.valor_plano) }}</div>{% endfor %}
{% else %}<div class="small">Nenhum cliente.</div>{% endif %}
</div>
{% endfor %}

<h2 class="section-title">👥 Clientes</h2>
<table><thead><tr><th>Nome</th><th>WhatsApp</th><th>Plano</th><th>Vencimento</th><th>Site</th><th>Criado em</th><th>Detalhes</th><th>Status</th><th>Ações</th></tr></thead><tbody>
{% for c in clientes %}<tr>
<td>{{ c.nome }}</td><td>{{ c.whatsapp }}</td><td>R$ {{ "%.2f"|format(c.valor_plano) }}</td><td>{{ c.data_vencimento }}</td><td>{% if c.site %}<a href="{{ c.site }}" target="_blank">Site</a>{% else %}-{% endif %}</td><td>{{ c.data_criacao_usuario or "-" }}</td><td>{{ c.detalhes_mac or "-" }}</td>
<td><span class="status {{ 'pago' if c.pago else 'pendente' }}">{{ 'Pago' if c.pago else 'Pendente' }}</span></td>
<td><div class="actions">
<a class="btn success" target="_blank" href="{{ whatsapp_link(c) }}">WhatsApp</a>
{% if not c.pago %}<form method="post" action="{{ url_for('pagar', id=c.id) }}"><button class="warn">Marcar pago</button></form>{% endif %}
<form method="post" action="{{ url_for('renovar', id=c.id) }}"><button class="primary">Renovar</button></form>
<form method="post" action="{{ url_for('excluir', id=c.id) }}" onsubmit="return confirm('Excluir este cliente?')"><button class="danger">Excluir</button></form>
</div></td></tr>{% endfor %}
</tbody></table>

<div class="mobile">
{% for c in clientes %}<div class="client">
<div class="client-head"><div><b>{{ c.nome }}</b><br><span class="small">{{ c.whatsapp }}</span></div>
<span class="status {{ 'pago' if c.pago else 'pendente' }}">{{ 'Pago' if c.pago else 'Pendente' }}</span></div>
<p>Plano: <b>R$ {{ "%.2f"|format(c.valor_plano) }}</b><br>Vencimento: <b>{{ c.data_vencimento }}</b></p>
{% if c.site %}<p>🌐 <a href="{{ c.site }}" target="_blank" rel="noopener">Site</a></p>{% endif %}
{% if c.data_criacao_usuario %}<p class="small">Criado em: {{ c.data_criacao_usuario }}</p>{% endif %}
{% if c.detalhes_mac %}<div class="alert"><b>Detalhes:</b><br>{{ c.detalhes_mac }}</div>{% endif %}
<div class="actions"><a class="btn success" target="_blank" href="{{ whatsapp_link(c) }}">WhatsApp</a>
{% if not c.pago %}<form method="post" action="{{ url_for('pagar', id=c.id) }}"><button class="warn">Pago</button></form>{% endif %}
<form method="post" action="{{ url_for('renovar', id=c.id) }}"><button class="primary">Renovar</button></form>
<form method="post" action="{{ url_for('excluir', id=c.id) }}"><button class="danger">Excluir</button></form></div>
</div>{% endfor %}
</div>
</main>
</body></html>
"""

def db_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL não configurada.")
    # Render/Supabase normalmente fornecem uma URL PostgreSQL pronta.
    if "sslmode=" not in url.lower():
        url += "&sslmode=require" if "?" in url else "?sslmode=require"
    return url

def conn():
    return psycopg2.connect(db_url(), connect_timeout=10)

def init_db():
    with conn() as c:
        with c.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS clientes (
                    id SERIAL PRIMARY KEY,
                    nome VARCHAR(150) NOT NULL,
                    whatsapp VARCHAR(30) NOT NULL,
                    valor_plano NUMERIC(12,2) NOT NULL DEFAULT 25.00,
                    data_vencimento DATE NOT NULL,
                    chave_pix VARCHAR(255) NOT NULL DEFAULT '06151758480',
                    site VARCHAR(500),
                    detalhes_mac TEXT,
                    data_criacao_usuario DATE,
                    pago INTEGER NOT NULL DEFAULT 0 CHECK (pago IN (0,1)),
                    data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
        c.commit()

def clean_phone(value):
    return re.sub(r"\D", "", value or "")

def money(v):
    return f"R$ {float(v):.2f}".replace(".", ",")

def mensagem_cobranca(c):
    d = c["data_vencimento"]
    if hasattr(d, "strftime"):
        d = d.strftime("%d/%m/%Y")
    return (f"Olá, {c['nome']}! 😊\n\n"
            f"Passando para lembrar da sua mensalidade no valor de {money(c['valor_plano'])}.\n"
            f"Vencimento: {d}.\n\n"
            f"Pagamento via Pix:\n{c['chave_pix']}\n\n"
            f"Obrigado!")

def whatsapp_link(c):
    phone = clean_phone(c["whatsapp"])
    return "https://wa.me/" + phone + "?text=" + quote(mensagem_cobranca(c))

@app.before_request
def prepare():
    if not hasattr(app, "_db_ready"):
        init_db()
        app._db_ready = True

@app.get("/")
def index():
    with conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM clientes ORDER BY data_vencimento, nome")
            clientes = cur.fetchall()
    hoje = date.today()
    pendentes = [x for x in clientes if not x["pago"]]
    pagos = [x for x in clientes if x["pago"]]
    total = sum(float(x["valor_plano"]) for x in pendentes)
    stats = [("Clientes", len(clientes)), ("Pendentes", len(pendentes)),
             ("Pagos", len(pagos)), ("A receber", money(total)),
             ("Vencem hoje", sum(1 for x in pendentes if x["data_vencimento"] == hoje))]
    grupos = [
        ("Vence em 3 a 5 dias", lambda d: 3 <= (d-hoje).days <= 5),
        ("Vence em 1 a 2 dias", lambda d: 1 <= (d-hoje).days <= 2),
        ("Vence hoje", lambda d: (d-hoje).days == 0),
        ("Vencido até 7 dias", lambda d: -7 <= (d-hoje).days <= -1),
        ("Vencido há mais de 7 dias", lambda d: (d-hoje).days < -7),
    ]
    alertas = [{"titulo": t, "clientes": [x for x in pendentes if fn(x["data_vencimento"])]} for t,fn in grupos]
    return render_template_string(HTML, clientes=clientes, stats=stats, alertas=alertas,
                                  pix=PIX_PADRAO, whatsapp_link=whatsapp_link, links=None)

@app.post("/clientes")
def add_cliente():
    nome = request.form.get("nome","").strip()
    whatsapp = clean_phone(request.form.get("whatsapp"))
    valor = request.form.get("valor_plano","25").replace(",", ".")
    venc = request.form.get("data_vencimento")
    pix = request.form.get("chave_pix","").strip() or PIX_PADRAO
    site = request.form.get("site","").strip()
    detalhes_mac = request.form.get("detalhes_mac","").strip()
    data_criacao_usuario = request.form.get("data_criacao_usuario","").strip() or None
    try:
        valor = float(valor)
        datetime.strptime(venc, "%Y-%m-%d")
        if not nome or not whatsapp or valor < 0: raise ValueError
        with conn() as c:
            with c.cursor() as cur:
                cur.execute("""INSERT INTO clientes
                    (nome,whatsapp,valor_plano,data_vencimento,chave_pix)
                    VALUES (%s,%s,%s,%s,%s)""", (nome,whatsapp,valor,venc,pix))
            c.commit()
        flash("Cliente cadastrado.")
    except ValueError:
        flash("Dados inválidos. Confira nome, WhatsApp, valor e vencimento.")
    except Exception as e:
        flash(f"Erro ao cadastrar: {e}")
    return redirect(url_for("index"))

@app.post("/clientes/<int:id>/pagar")
def pagar(id):
    with conn() as c:
        with c.cursor() as cur: cur.execute("UPDATE clientes SET pago=1 WHERE id=%s",(id,))
        c.commit()
    return redirect(url_for("index"))

def next_month_same_day(d):
    y = d.year + (1 if d.month == 12 else 0)
    m = 1 if d.month == 12 else d.month + 1
    return date(y,m,min(d.day,monthrange(y,m)[1]))

@app.post("/clientes/<int:id>/renovar")
def renovar(id):
    with conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT data_vencimento FROM clientes WHERE id=%s",(id,))
            row = cur.fetchone()
            if not row: return redirect(url_for("index"))
            nova = next_month_same_day(row["data_vencimento"])
            cur.execute("UPDATE clientes SET data_vencimento=%s,pago=0 WHERE id=%s",(nova,id))
        c.commit()
    return redirect(url_for("index"))

@app.post("/clientes/<int:id>/excluir")
def excluir(id):
    with conn() as c:
        with c.cursor() as cur: cur.execute("DELETE FROM clientes WHERE id=%s",(id,))
        c.commit()
    return redirect(url_for("index"))

@app.post("/notificar-todos")
def notificar_todos():
    mensagem = request.form.get("mensagem","").strip()
    with conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM clientes ORDER BY nome")
            clientes = cur.fetchall()
    links = [{"nome":x["nome"],"link":"https://wa.me/"+clean_phone(x["whatsapp"])+"?text="+quote(mensagem.replace("{nome}",x["nome"]))} for x in clientes]
    # Renderiza a mesma página com links; reaproveita lógica da home.
    hoje=date.today(); pendentes=[x for x in clientes if not x["pago"]]; pagos=[x for x in clientes if x["pago"]]
    total=sum(float(x["valor_plano"]) for x in pendentes)
    stats=[("Clientes",len(clientes)),("Pendentes",len(pendentes)),("Pagos",len(pagos)),("A receber",money(total)),("Vencem hoje",sum(1 for x in pendentes if x["data_vencimento"]==hoje))]
    grupos=[("Vence em 3 a 5 dias",lambda d:3<=(d-hoje).days<=5),("Vence em 1 a 2 dias",lambda d:1<=(d-hoje).days<=2),("Vence hoje",lambda d:(d-hoje).days==0),("Vencido até 7 dias",lambda d:-7<=(d-hoje).days<=-1),("Vencido há mais de 7 dias",lambda d:(d-hoje).days<-7)]
    alertas=[{"titulo":t,"clientes":[x for x in pendentes if fn(x["data_vencimento"])]} for t,fn in grupos]
    return render_template_string(HTML,clientes=clientes,stats=stats,alertas=alertas,pix=PIX_PADRAO,whatsapp_link=whatsapp_link,links=links)

@app.get("/health")
def health():
    with conn() as c:
        with c.cursor() as cur: cur.execute("SELECT 1")
    return {"status":"online","database":"ok"}

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=False)
