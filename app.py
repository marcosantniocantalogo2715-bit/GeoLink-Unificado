import os
import sqlite3
import math
import requests

from datetime import datetime, timezone

from flask import (
    Flask,
    jsonify,
    request,
    send_from_directory,
    redirect,
    url_for,
    session,
    render_template_string
)

from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv


# =========================
# CONFIGURAÇÕES
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "geocheckin.db")

load_dotenv(os.path.join(BASE_DIR, ".env"))

app = Flask(
    __name__,
    static_folder="web",
    static_url_path="/web"
)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "chave-temporaria-trocar-depois"
)

# Token do IPinfo
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")


# =========================
# GOOGLE OAUTH
# =========================

oauth = OAuth(app)

google = oauth.register(
    name="google",

    client_id=os.getenv(
        "GOOGLE_CLIENT_ID"
    ),

    client_secret=os.getenv(
        "GOOGLE_CLIENT_SECRET"
    ),

    server_metadata_url=(
        "https://accounts.google.com/"
        ".well-known/openid-configuration"
    ),

    client_kwargs={
        "scope": "openid email profile",

        "token_endpoint_auth_method":
            "client_secret_post",
    },
)


# =========================
# BANCO DE DADOS
# =========================

def db():

    conn = sqlite3.connect(
        DB_PATH
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    os.makedirs(
        os.path.dirname(DB_PATH),
        exist_ok=True
    )

    conn = db()

    cur = conn.cursor()


    cur.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY,
            titulo TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            raio_metros REAL NOT NULL,
            ativo INTEGER NOT NULL
        )
    """)


    cur.execute("""
        CREATE TABLE IF NOT EXISTS checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            evento_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            distancia_metros REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,

            UNIQUE(
                tenant_id,
                user_id,
                evento_id
            ),

            FOREIGN KEY(evento_id)
                REFERENCES eventos(id)
        )
    """)


    # =========================
    # NOVA TABELA DE DISPOSITIVOS
    # =========================

    cur.execute("""
        CREATE TABLE IF NOT EXISTS dispositivos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL UNIQUE,
            device_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
    """)


    cur.execute("""
        INSERT OR IGNORE INTO eventos
        (
            id,
            titulo,
            latitude,
            longitude,
            raio_metros,
            ativo
        )

        VALUES (
            1,
            'Aula Corporativa',
            -15.793889,
            -47.882778,
            30,
            1
        )
    """)


    cur.execute("""
        INSERT OR IGNORE INTO eventos
        (
            id,
            titulo,
            latitude,
            longitude,
            raio_metros,
            ativo
        )

        VALUES (
            2,
            'Evento Inativo',
            -15.793889,
            -47.882778,
            30,
            0
        )
    """)


    conn.commit()
    conn.close()


# =========================
# FUNÇÕES AUXILIARES
# =========================

def event_dict(row):

    return {

        "id":
            row["id"],

        "titulo":
            row["titulo"],

        "latitude":
            row["latitude"],

        "longitude":
            row["longitude"],

        "raioMetros":
            row["raio_metros"],

        "ativo":
            bool(row["ativo"]),
    }


def haversine(
    lat1,
    lon1,
    lat2,
    lon2
):

    R = 6371000

    p = math.pi / 180

    dlat = (
        lat2 - lat1
    ) * p

    dlon = (
        lon2 - lon1
    ) * p

    a = (

        math.sin(
            dlat / 2
        ) ** 2

        +

        math.cos(
            lat1 * p
        )

        *

        math.cos(
            lat2 * p
        )

        *

        math.sin(
            dlon / 2
        ) ** 2
    )

    return (
        R
        *
        2
        *
        math.asin(
            math.sqrt(a)
        )
    )


def api_error(
    message,
    status,
    **extra
):

    payload = {
        "erro": message
    }

    payload.update(
        extra
    )

    return jsonify(
        payload
    ), status


# =========================
# VERIFICAÇÃO DE VPN
# IPINFO
# =========================

def verificar_vpn():

    ip = request.remote_addr

    forwarded = request.headers.get(
        "X-Forwarded-For"
    )

    if forwarded:

        ip = forwarded.split(
            ","
        )[0].strip()


    if not ip:

        return False, {
            "erro":
                "Não foi possível identificar o IP."
        }


    # =========================
    # TESTE LOCAL
    # =========================

    if ip in (
        "127.0.0.1",
        "::1",
        "localhost"
    ):

        return False, {
            "ip": ip,
            "local": True
        }


    # =========================
    # TOKEN
    # =========================

    if not IPINFO_TOKEN:

        return False, {
            "ip": ip,

            "erro":
                "IPINFO_TOKEN não configurado."
        }


    # =========================
    # CONSULTA IPINFO
    # =========================

    try:

        resposta = requests.get(

            f"https://ipinfo.io/{ip}",

            params={
                "token":
                    IPINFO_TOKEN
            },

            timeout=5
        )

    except requests.RequestException as exc:

        return False, {
            "ip": ip,

            "erro":
                f"Erro ao consultar IPinfo: {exc}"
        }


    if resposta.status_code != 200:

        return False, {

            "ip": ip,

            "erro":
                "IPinfo não conseguiu "
                "consultar este IP.",

            "status_code":
                resposta.status_code
        }


    try:

        dados = resposta.json()

    except ValueError:

        return False, {

            "ip": ip,

            "erro":
                "Resposta inválida do IPinfo."
        }


    anonymous = dados.get(
        "anonymous",
        {}
    )


    vpn = bool(
        anonymous.get(
            "is_vpn",
            False
        )
    )


    proxy = bool(
        anonymous.get(
            "is_proxy",
            False
        )
    )


    tor = bool(
        anonymous.get(
            "is_tor",
            False
        )
    )


    relay = bool(
        anonymous.get(
            "is_relay",
            False
        )
    )


    residential_proxy = bool(
        anonymous.get(
            "is_res_proxy",
            False
        )
    )


    hosting = bool(
        dados.get(
            "is_hosting",
            False
        )
    )


    bloqueado = (

        vpn
        or proxy
        or tor
        or relay
        or residential_proxy
    )


    resultado = {

        "ip":
            ip,

        "vpn":
            vpn,

        "proxy":
            proxy,

        "tor":
            tor,

        "relay":
            relay,

        "residential_proxy":
            residential_proxy,

        "hosting":
            hosting,

        "service":
            anonymous.get(
                "name"
            )
    }


    return bloqueado, resultado


# =========================
# LOGIN GOOGLE
# =========================

@app.route("/login")
def login():

    redirect_uri = url_for(
        "authorize",
        _external=True
    )

    return google.authorize_redirect(
        redirect_uri
    )


@app.route("/authorize")
def authorize():

    try:

        token = (
            google
            .authorize_access_token()
        )

        user = token.get(
            "userinfo"
        )


        if not user:

            user = google.userinfo(
                token=token
            )


    except Exception as exc:

        return (
            f"Falha no login Google: {exc}",
            400
        )


    if not user:

        return (
            "Não foi possível obter "
            "os dados do usuário do Google.",
            403
        )


    email = str(
        user.get(
            "email",
            ""
        )
    ).strip().lower()


    if not email:

        return (
            "O Google não informou um e-mail.",
            403
        )


    # =========================
    # DOMÍNIOS PERMITIDOS
    # =========================

    DOMINIOS_PERMITIDOS = [

        "@alunos.unicerrado.edu.br",

        "@professor.unicerrado.edu.br",

        "@professores.unicerrado.edu.br",

    ]


    permitido = any(

        email.endswith(
            dominio
        )

        for dominio
        in DOMINIOS_PERMITIDOS
    )


    if not permitido:

        session.clear()


        return render_template_string("""
        <!DOCTYPE html>

        <html lang="pt-BR">

        <head>

            <meta charset="UTF-8">

            <meta
                name="viewport"
                content="width=device-width, initial-scale=1.0"
            >

            <title>Acesso negado</title>

            <style>

                body {
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background: #f4f6f8;

                    display: flex;
                    justify-content: center;
                    align-items: center;

                    min-height: 100vh;
                }

                .box {
                    width: 420px;
                    max-width: 90%;

                    background: white;

                    padding: 40px;

                    border-radius: 18px;

                    text-align: center;

                    box-shadow:
                        0 8px 30px
                        rgba(0,0,0,.12);
                }

                .icon {
                    font-size: 55px;
                }

                h1 {
                    color: #d93025;
                    margin-bottom: 10px;
                }

                p {
                    color: #555;
                    line-height: 1.5;
                }

                .email {
                    font-weight: bold;
                    word-break: break-word;
                }

                a {
                    display: inline-block;

                    margin-top: 20px;

                    padding: 12px 22px;

                    background: #111;

                    color: white;

                    text-decoration: none;

                    border-radius: 8px;
                }

            </style>

        </head>


        <body>

            <div class="box">

                <div class="icon">
                    🚫
                </div>

                <h1>
                    Acesso negado
                </h1>

                <p>
                    Este sistema é exclusivo
                    para usuários com e-mail
                    institucional da UNICERRADO.
                </p>

                <p class="email">

                    E-mail utilizado:

                    <br>

                    {{ email }}

                </p>

                <p>

                    Permitidos somente:

                    <br><br>

                    <strong>
                        @alunos.unicerrado.edu.br
                    </strong>

                    <br>

                    <strong>
                        @professor.unicerrado.edu.br
                    </strong>

                    <br>

                    <strong>
                        @professores.unicerrado.edu.br
                    </strong>

                </p>

                <a href="/logout">
                    Voltar
                </a>

            </div>

        </body>

        </html>

        """,
        email=email
        ), 403


    # =========================
    # CRIAÇÃO DA SESSÃO
    # =========================

    session.clear()


    session["user"] = {

        "sub":
            user.get(
                "sub",
                ""
            ),

        "name":
            user.get(
                "name",
                ""
            ),

        "email":
            email,

        "picture":
            user.get(
                "picture",
                ""
            ),

        "email_verified":
            bool(
                user.get(
                    "email_verified",
                    False
                )
            ),
    }


    return redirect(
        url_for("home")
    )


# =========================
# USUÁRIO LOGADO
# =========================

@app.get("/api/me")
def api_me():

    user = session.get(
        "user"
    )


    if not user:

        return api_error(
            "Usuário não autenticado",
            401
        )


    return jsonify({

        "authenticated":
            True,

        "name":
            user.get(
                "name",
                ""
            ),

        "email":
            user.get(
                "email",
                ""
            ),

        "picture":
            user.get(
                "picture",
                ""
            ),

        "emailVerified":
            bool(
                user.get(
                    "email_verified",
                    False
                )
            ),

    })


# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.pop(
        "user",
        None
    )

    return redirect(
        url_for("home")
    )


# =========================
# PÁGINA PRINCIPAL
# =========================

@app.route("/")
def home():

    if "user" not in session:

        return render_template_string("""
<!doctype html>

<html lang="pt-BR">

<head>

<meta charset="utf-8">

<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

<title>GeoCheckIn - Acesso</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;

    font-family: Arial, sans-serif;

    background: #f4f6f8;

    min-height: 100vh;

    display: flex;

    align-items: center;

    justify-content: center;
}

.box {

    width: 400px;

    max-width: 90%;

    background: #fff;

    padding: 40px;

    border-radius: 18px;

    text-align: center;

    box-shadow:
        0 8px 30px
        rgba(0,0,0,.12);
}

.logo {
    font-size: 45px;
}

.sub {
    color: #666;
}

.institution {

    margin: 25px 0;

    padding: 12px;

    background: #f1f3f4;

    border-radius: 10px;

    color: #444;

    font-size: 14px;
}

.google {

    display: flex;

    align-items: center;

    justify-content: center;

    gap: 12px;

    width: 100%;

    padding: 13px;

    border: 1px solid #dadce0;

    border-radius: 8px;

    background: #fff;

    color: #3c4043;

    font-size: 16px;

    font-weight: bold;

    text-decoration: none;
}

.footer {

    margin-top: 25px;

    font-size: 12px;

    color: #888;
}

</style>

</head>

<body>

<div class="box">

    <div class="logo">
        📍
    </div>

    <h1>
        GeoCheckIn
    </h1>

    <p class="sub">
        Acesso institucional
    </p>

    <div class="institution">

        Use somente seu e-mail
        institucional da UNICERRADO.

    </div>

    <a
        class="google"
        href="{{ url_for('login') }}"
    >

        Entrar com Google

    </a>

    <div class="footer">

        GeoCheckIn • Controle de frequência

    </div>

</div>

</body>

</html>
""")


    return send_from_directory(
        app.static_folder,
        "index.html"
    )


# =========================
# FAVICON
# =========================

@app.route("/favicon.ico")
def favicon():

    return "", 204


# =========================
# API
# =========================

@app.get("/api/health")
def health():

    return jsonify({
        "status": "ok"
    })


@app.get("/api/v1/eventos")
def eventos():

    conn = db()


    rows = conn.execute(
        "SELECT * FROM eventos ORDER BY id"
    ).fetchall()


    conn.close()


    return jsonify([

        event_dict(r)

        for r in rows

    ])


@app.get(
    "/api/v1/eventos/<int:evento_id>"
)
def evento(evento_id):

    conn = db()


    row = conn.execute(
        "SELECT * FROM eventos WHERE id=?",
        (evento_id,)
    ).fetchone()


    conn.close()


    if not row:

        return api_error(
            "Evento não encontrado",
            404
        )


    return jsonify(
        event_dict(row)
    )


# =========================
# CHECK-IN
# =========================

@app.post("/api/v1/checkin")
def checkin():

    # =========================
    # BLOQUEIO DE VPN
    # =========================

    bloqueado, motivo = verificar_vpn()


    if bloqueado:

        return api_error(

            "Check-in bloqueado. "
            "VPN, proxy, Tor ou relay "
            "detectado.",

            403,

            motivo=motivo
        )


    # =========================
    # TENANT
    # =========================

    tenant = (

        request.headers
        .get(
            "X-Tenant-ID",
            ""
        )
        .strip()

        or "unicerrado"
    )


    # =========================
    # USUÁRIO DA SESSÃO
    # =========================

    session_user = (
        session.get("user")
        or {}
    )


    user = str(

        session_user.get(
            "email",
            ""
        )

    ).strip().lower()


    if not user:

        return api_error(

            "Usuário não autenticado. "
            "Faça login com Google "
            "antes do check-in.",

            401
        )


    # =========================
    # DADOS
    # =========================

    data = request.get_json(
        silent=True
    )


    if not isinstance(
        data,
        dict
    ):

        return api_error(
            "JSON inválido ou ausente",
            400
        )


    # =========================
    # DEVICE ID
    # =========================

    device_id = str(
        data.get(
            "deviceId",
            ""
        )
    ).strip()


    if not device_id:

        return api_error(

            "Não foi possível identificar "
            "este dispositivo. "
            "Atualize a página e tente novamente.",

            400
        )


    # =========================
    # BANCO
    # =========================

    conn = db()


    # =========================
    # VERIFICA SE A CONTA
    # JÁ POSSUI DISPOSITIVO
    # =========================

    dispositivo = conn.execute(

        """
        SELECT *
        FROM dispositivos
        WHERE user_id=?
        """,

        (user,)

    ).fetchone()


    # =========================
    # PRIMEIRO DISPOSITIVO
    # =========================

    if not dispositivo:

        agora = datetime.now(
            timezone.utc
        ).isoformat()


        conn.execute(

            """
            INSERT INTO dispositivos
            (
                tenant_id,
                user_id,
                device_id,
                created_at,
                last_seen_at
            )

            VALUES (
                ?, ?, ?, ?, ?
            )
            """,

            (
                tenant,
                user,
                device_id,
                agora,
                agora
            )
        )


        conn.commit()


        dispositivo = conn.execute(

            """
            SELECT *
            FROM dispositivos
            WHERE user_id=?
            """,

            (user,)

        ).fetchone()


    # =========================
    # OUTRO DISPOSITIVO
    # =========================

    if dispositivo["device_id"] != device_id:

        conn.close()

        return api_error(

            "Este dispositivo não está "
            "autorizado para esta conta. "
            "A conta já está vinculada "
            "a outro dispositivo.",

            403
        )


    # =========================
    # ATUALIZA ÚLTIMO ACESSO
    # =========================

    agora = datetime.now(
        timezone.utc
    ).isoformat()


    conn.execute(

        """
        UPDATE dispositivos

        SET last_seen_at=?

        WHERE user_id=?
        """,

        (
            agora,
            user
        )
    )


    conn.commit()


    # =========================
    # TOKEN DE INTEGRIDADE
    # =========================

    token = str(

        data.get(
            "integrityToken",
            ""
        )

    ).strip()


    if token != "DEVICE_OK":

        conn.close()

        return api_error(

            "Token de integridade "
            "inválido para este protótipo",

            403
        )


    # =========================
    # EVENTO
    # =========================

    evento_id = data.get(
        "eventoId"
    )


    if evento_id is None:

        conn.close()

        return api_error(
            "eventoId é obrigatório",
            400
        )


    # =========================
    # LOCALIZAÇÃO
    # =========================

    try:

        lat = float(
            data.get(
                "latitude"
            )
        )


        lon = float(
            data.get(
                "longitude"
            )
        )


    except (
        TypeError,
        ValueError
    ):

        conn.close()

        return api_error(

            "Latitude e longitude "
            "devem ser números",

            422
        )


    if not -90 <= lat <= 90:

        conn.close()

        return api_error(

            "Latitude inválida. "
            "Use um valor entre -90 e 90",

            422
        )


    if not -180 <= lon <= 180:

        conn.close()

        return api_error(

            "Longitude inválida. "
            "Use um valor entre -180 e 180",

            422
        )


    # =========================
    # BUSCA EVENTO
    # =========================

    row = conn.execute(

        "SELECT * FROM eventos WHERE id=?",

        (evento_id,)

    ).fetchone()


    if not row:

        conn.close()

        return api_error(
            "Evento não encontrado",
            404
        )


    # =========================
    # EVENTO ATIVO
    # =========================

    if not row["ativo"]:

        conn.close()

        return api_error(
            "Evento está inativo",
            409
        )


    # =========================
    # CHECK-IN DUPLICADO
    # =========================

    duplicate = conn.execute(

        """
        SELECT id
        FROM checkins

        WHERE tenant_id=?
        AND user_id=?
        AND evento_id=?
        """,

        (
            tenant,
            user,
            evento_id
        )

    ).fetchone()


    if duplicate:

        conn.close()

        return api_error(

            "Este usuário já possui "
            "check-in neste evento.",

            409
        )


    # =========================
    # DISTÂNCIA
    # =========================

    distance = haversine(

        lat,
        lon,

        row["latitude"],
        row["longitude"]

    )


    if distance > row["raio_metros"]:

        conn.close()

        return api_error(

            "Usuário está fora "
            "do raio permitido",

            400,

            distanciaMetros=round(
                distance,
                2
            ),

            raioMetros=row[
                "raio_metros"
            ],
        )


    # =========================
    # CRIAÇÃO DO CHECK-IN
    # =========================

    created = datetime.now(
        timezone.utc
    ).isoformat()


    conn.execute(

        """
        INSERT INTO checkins
        (
            tenant_id,
            user_id,
            evento_id,
            latitude,
            longitude,
            distancia_metros,
            status,
            created_at
        )

        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,

        (
            tenant,
            user,
            evento_id,
            lat,
            lon,
            distance,
            "PRESENCA_CONFIRMADA",
            created
        )
    )


    conn.commit()

    conn.close()


    # =========================
    # RESPOSTA
    # =========================

    return jsonify({

        "mensagem":
            "Check-in realizado "
            "com sucesso!",

        "evento":
            row["titulo"],

        "usuario":
            user,

        "distanciaMetros":
            round(
                distance,
                2
            ),

        "raioMetros":
            row["raio_metros"],

        "status":
            "PRESENCA_CONFIRMADA",

        "createdAt":
            created,

    }), 200


# =========================
# ERRO 404
# =========================

@app.errorhandler(404)
def not_found(_):

    return api_error(

        "Rota não encontrada",

        404
    )


# =========================
# INICIALIZAÇÃO
# =========================

init_db()


if __name__ == "__main__":

    print(
        "GeoCheckIn iniciado!"
    )

    print(
        "Abra: http://192.168.0.100:5000"
    )

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )