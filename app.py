"""
SD Digital Solutions — Servidor Automático
==========================================
Recibe datos del formulario web → genera PDF XCG → envía por email

Deploy en Railway.app (gratis)
"""

import os, io, json, smtplib, traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

# ── Importar el generador de PDF ─────────────────────────────────────────────
from fill_xcg_form import fill_xcg_form_bytes

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, 
     supports_credentials=False,
     allow_headers=["Content-Type"],
     methods=["GET", "POST", "OPTIONS"])

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    return response

# ── Configuración (variables de entorno en Railway) ──────────────────────────
# ADMIN_EMAIL puede ser uno o varios separados por coma:
# ej: "ramiro.olbina@gmail.com,otro@gmail.com,tercero@hotmail.com"
_admin_raw   = os.environ.get("ADMIN_EMAIL", "ramiro.olbina@gmail.com")
ADMIN_EMAILS = [e.strip() for e in _admin_raw.split(",") if e.strip()]
GMAIL_USER     = os.environ.get("GMAIL_USER",     "")
GMAIL_PASSWORD = os.environ.get("GMAIL_PASSWORD", "")
PDF_BASE_PATH  = os.path.join(os.path.dirname(__file__), "formulario_xcg_base.pdf")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "SD Digital Solutions PDF Generator"})


@app.route("/submit", methods=["POST"])
def submit():
    """
    Endpoint principal. Recibe JSON con datos del cliente,
    genera el PDF XCG pre-llenado y lo envía por email.
    """
    try:
        raw = request.get_json(force=True)
        if not raw:
            return jsonify({"error": "No data received"}), 400

        # ── Mapear campos del formulario web al formato XCG ───────────────────
        data = map_form_to_xcg(raw)

        # ── Generar PDF en memoria ─────────────────────────────────────────────
        pdf_bytes = fill_xcg_form_bytes(data, PDF_BASE_PATH)

        # ── Nombre del archivo ─────────────────────────────────────────────────
        nombre_completo = f"{data.get('achternaam','')} {data.get('voornamen','')}".strip()
        fecha_hoy = datetime.now().strftime("%Y%m%d")
        filename = f"XCG_{nombre_completo.replace(' ','_')}_{fecha_hoy}.pdf"

        # ── Enviar email con PDF adjunto ───────────────────────────────────────
        if GMAIL_USER and GMAIL_PASSWORD:
            send_email_with_pdf(
                to=ADMIN_EMAILS,
                subject=f"🇨🇼 Nuevo cliente XCG: {nombre_completo}",
                body=build_email_body(data),
                pdf_bytes=pdf_bytes,
                filename=filename
            )
            email_status = "sent"
        else:
            email_status = "skipped (no email config)"

        return jsonify({
            "result":  "success",
            "cliente": nombre_completo,
            "email":   email_status,
            "pdf":     filename
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def map_form_to_xcg(raw):
    """
    Convierte los campos del formulario web (español)
    al formato que espera fill_xcg_form (neerlandés/XCG).
    """
    # Mapear hijos → kinderen
    hijos_raw = raw.get("hijos", [])
    kinderen = []
    for h in (hijos_raw if isinstance(hijos_raw, list) else []):
        if isinstance(h, dict):
            kinderen.append({
                "naam":          h.get("nombre", ""),
                "geboortedatum": h.get("fecha",  ""),
                "geboorteland":  h.get("pais",   ""),
                "nationaliteit": h.get("nacionalidad", ""),
            })

    # Estado civil → gehuwd
    estado = raw.get("estadoCivil", "soltero").lower()
    gehuwd = "ja" if "casad" in estado or "uni" in estado else "nee"

    return {
        # Datos principales
        "achternaam":           raw.get("apellido",        ""),
        "voornamen":            raw.get("nombre",          ""),
        "geboortedatum":        raw.get("fechaNacimiento", ""),
        "geboorteland":         raw.get("paisNacimiento",  ""),
        "geboorteplaats":       raw.get("lugarNacimiento", ""),
        "nationaliteit":        raw.get("nacionalidad",    ""),
        "fmscrv":               raw.get("fmscrv",          ""),

        # Dirección origen
        "adres_buitenland":     raw.get("direccion",       ""),
        "woonplaats":           raw.get("ciudad",          ""),
        "land":                 raw.get("pais",            ""),

        # Curaçao
        "verblijfsadres_curacao": raw.get("direccionCuracao", ""),
        "postadres_curacao":      raw.get("postadresCuracao", ""),

        # Contacto
        "telefoon":             raw.get("telefono",        ""),
        "email":                raw.get("email",           ""),

        # Pasaporte
        "paspoort_nr":          raw.get("pasaporte",       ""),
        "plaats_uitgifte":      raw.get("lugarExpedicion", ""),
        "datum_uitgifte":       raw.get("fechaExpedicion", ""),
        "geldig_tot":           raw.get("validoHasta",     ""),

        # Género
        "geslacht":             raw.get("genero", "M").upper(),

        # Estado civil
        "gehuwd":               gehuwd,
        "datum_huwelijk":       raw.get("fechaMatrimonio", ""),

        # Pareja
        "partner_achternaam":   raw.get("nombreConyuge",  ""),
        "partner_voornamen":    "",
        "partner_geboortedatum": raw.get("fechaNacimientoConyuge", ""),
        "partner_geboorteland": "",
        "partner_geboorteplaats": "",
        "partner_nationaliteit": "",

        # Hijos
        "kinderen": kinderen,

        # Trabajo
        "beroep": raw.get("ocupacion", ""),
    }


def send_email_with_pdf(to, subject, body, pdf_bytes, filename):
    """Envía email con el PDF como adjunto usando Gmail SMTP.
    to puede ser un string o una lista de emails."""
    if isinstance(to, str):
        to = [t.strip() for t in to.split(",") if t.strip()]
    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(to)
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Adjuntar PDF
    pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(pdf_part)

    # Enviar via Gmail SMTP
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(GMAIL_USER, GMAIL_PASSWORD)
        smtp.sendmail(GMAIL_USER, to, msg.as_string())  # to is a list


def build_email_body(data):
    """Construye el cuerpo del email con los datos del cliente."""
    k = data.get("kinderen", [])
    hijos_txt = "\n".join(
        f"  {i+1}. {h['naam']} — {h['geboortedatum']}"
        for i, h in enumerate(k)
    ) if k else "  —"

    return f"""
SD Digital Solutions — Nuevo Registro de Cliente
=================================================
Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}

DATOS PERSONALES
─────────────────────────────────────
Apellido       : {data.get('achternaam','')}
Nombre         : {data.get('voornamen','')}
Fecha Nac.     : {data.get('geboortedatum','')}
País Nac.      : {data.get('geboorteland','')}
Lugar Nac.     : {data.get('geboorteplaats','')}
Nacionalidad   : {data.get('nationaliteit','')}

PASAPORTE
─────────────────────────────────────
Número         : {data.get('paspoort_nr','')}
Lugar expedic. : {data.get('plaats_uitgifte','')}
Fecha expedic. : {data.get('datum_uitgifte','')}
Válido hasta   : {data.get('geldig_tot','')}

CONTACTO
─────────────────────────────────────
Teléfono       : {data.get('telefoon','')}
Email          : {data.get('email','')}

DIRECCIÓN ORIGEN
─────────────────────────────────────
Dirección      : {data.get('adres_buitenland','')}
Ciudad         : {data.get('woonplaats','')}
País           : {data.get('land','')}

CURAÇAO
─────────────────────────────────────
Dirección      : {data.get('verblijfsadres_curacao','')}
Ocupación      : {data.get('beroep','')}

FAMILIA
─────────────────────────────────────
Estado civil   : {data.get('gehuwd','')}
Cónyuge        : {data.get('partner_achternaam','')}
Fecha mat.     : {data.get('datum_huwelijk','')}

Hijos:
{hijos_txt}

─────────────────────────────────────
El formulario XCG pre-llenado se adjunta a este email.
SD Digital Solutions
""".strip()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
