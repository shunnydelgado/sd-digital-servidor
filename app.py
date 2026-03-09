"""
SD Digital Solutions — Servidor Automático
==========================================
Recibe datos del formulario web → genera PDF XCG → envía por email via SendGrid
"""

import os, io, json, traceback, base64, requests
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from fill_xcg_form import fill_xcg_form_bytes

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}},
     allow_headers=["Content-Type"],
     methods=["GET", "POST", "OPTIONS"])

@app.after_request
def after_request(response):
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    return response

# ── Variables de entorno ──────────────────────────────────────────────────────
_admin_raw      = os.environ.get("ADMIN_EMAIL", "famolbinadelgado@gmail.com")
ADMIN_EMAILS    = [e.strip() for e in _admin_raw.split(",") if e.strip()]
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL    = os.environ.get("SENDER_EMAIL", "famolbinadelgado@gmail.com")
PDF_BASE_PATH   = os.path.join(os.path.dirname(__file__), "formulario_xcg_base.pdf")


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "SD Digital Solutions PDF Generator"})


@app.route("/submit", methods=["POST", "OPTIONS"])
def submit():
    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200
    try:
        raw = request.get_json(force=True)
        if not raw:
            return jsonify({"error": "No data received"}), 400

        data = map_form_to_xcg(raw)
        pdf_bytes = fill_xcg_form_bytes(data, PDF_BASE_PATH)

        nombre_completo = f"{data.get('achternaam','')} {data.get('voornamen','')}".strip()
        fecha_hoy = datetime.now().strftime("%Y%m%d")
        filename = f"XCG_{nombre_completo.replace(' ','_')}_{fecha_hoy}.pdf"

        if SENDGRID_API_KEY:
            send_email_sendgrid(
                to=ADMIN_EMAILS,
                subject=f"🇨🇼 Nuevo cliente XCG: {nombre_completo}",
                body=build_email_body(data),
                pdf_bytes=pdf_bytes,
                filename=filename
            )
            email_status = "sent"
        else:
            email_status = "skipped (no SENDGRID_API_KEY)"

        return jsonify({"result": "success", "cliente": nombre_completo, "email": email_status})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def send_email_sendgrid(to, subject, body, pdf_bytes, filename):
    """Envía email con PDF adjunto via SendGrid HTTP API."""
    if isinstance(to, str):
        to = [t.strip() for t in to.split(",") if t.strip()]

    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    payload = {
        "personalizations": [{"to": [{"email": e} for e in to]}],
        "from": {"email": SENDER_EMAIL, "name": "SD Digital Solutions"},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
        "attachments": [{
            "content": pdf_b64,
            "type": "application/pdf",
            "filename": filename,
            "disposition": "attachment"
        }]
    }

    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=30
    )

    if response.status_code not in (200, 202):
        raise Exception(f"SendGrid error {response.status_code}: {response.text}")


def map_form_to_xcg(raw):
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

    estado = raw.get("estadoCivil", "soltero").lower()
    gehuwd = "ja" if "casad" in estado or "uni" in estado else "nee"

    return {
        "achternaam":             raw.get("apellido",        ""),
        "voornamen":              raw.get("nombre",          ""),
        "geboortedatum":          raw.get("fechaNacimiento", ""),
        "geboorteland":           raw.get("paisNacimiento",  ""),
        "geboorteplaats":         raw.get("lugarNacimiento", ""),
        "nationaliteit":          raw.get("nacionalidad",    ""),
        "fmscrv":                 raw.get("fmscrv",          ""),
        "adres_buitenland":       raw.get("direccion",       ""),
        "woonplaats":             raw.get("ciudad",          ""),
        "land":                   raw.get("pais",            ""),
        "verblijfsadres_curacao": raw.get("direccionCuracao",""),
        "postadres_curacao":      raw.get("postadresCuracao",""),
        "telefoon":               raw.get("telefono",        ""),
        "email":                  raw.get("email",           ""),
        "paspoort_nr":            raw.get("pasaporte",       ""),
        "plaats_uitgifte":        raw.get("lugarExpedicion", ""),
        "datum_uitgifte":         raw.get("fechaExpedicion", ""),
        "geldig_tot":             raw.get("validoHasta",     ""),
        "geslacht":               raw.get("genero", "M").upper(),
        "gehuwd":                 gehuwd,
        "datum_huwelijk":         raw.get("fechaMatrimonio", ""),
        "partner_achternaam":     raw.get("nombreConyuge",   ""),
        "partner_voornamen":      "",
        "partner_geboortedatum":  raw.get("fechaNacimientoConyuge", ""),
        "partner_geboorteland":   "",
        "partner_geboorteplaats": "",
        "partner_nationaliteit":  "",
        "kinderen":               kinderen,
        "beroep":                 raw.get("ocupacion", ""),
    }


def build_email_body(data):
    k = data.get("kinderen", [])
    hijos_txt = "\n".join(
        f"  {i+1}. {h['naam']} — {h['geboortedatum']}" for i, h in enumerate(k)
    ) if k else "  —"

    return f"""
SD Digital Solutions — Nuevo Registro
======================================
Fecha: {datetime.now().strftime("%d/%m/%Y %H:%M")}

Apellido    : {data.get('achternaam','')}
Nombre      : {data.get('voornamen','')}
Nacimiento  : {data.get('geboortedatum','')}
Nacionalidad: {data.get('nationaliteit','')}
Pasaporte   : {data.get('paspoort_nr','')}
Teléfono    : {data.get('telefoon','')}
Email       : {data.get('email','')}
Dirección   : {data.get('adres_buitenland','')}
Curaçao     : {data.get('verblijfsadres_curacao','')}
Estado civil: {data.get('gehuwd','')}
Cónyuge     : {data.get('partner_achternaam','')}
Hijos:
{hijos_txt}

El formulario XCG pre-llenado se adjunta a este email.
""".strip()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
