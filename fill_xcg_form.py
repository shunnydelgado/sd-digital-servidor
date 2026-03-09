"""
Generador de PDF XCG — SD Digital Solutions
Versión que retorna bytes (para uso en servidor web)
"""
import io, json, sys
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

PDF_W = 595.32
PDF_H = 841.92

def px(x): return x
def py(top, bottom):
    return PDF_H - (top + bottom) / 2

def create_overlay(data):
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(PDF_W, PDF_H))
    c.setFont("Helvetica", 8)

    # ── PÁGINA 1 ─────────────────────────────────────────────────────────────
    c.drawString(px(72), py(269, 288), "X")  # eerste aanvraag
    if data.get('datum_storting'):
        c.drawString(px(170), py(682, 692), data['datum_storting'])
    c.showPage()

    # ── PÁGINA 2 ─────────────────────────────────────────────────────────────
    EX = 170
    c.drawString(EX, py(208,218), data.get('achternaam', ''))
    if data.get('geslacht', 'M') == 'V':
        c.drawString(520, py(208,218), "X")
    else:
        c.drawString(477, py(208,218), "X")

    c.drawString(EX, py(228,238), data.get('voornamen', ''))
    c.drawString(EX, py(248,258), data.get('geboortedatum', ''))
    c.drawString(383, py(248,258), data.get('geboorteland', ''))
    c.drawString(EX, py(268,277), data.get('geboorteplaats', ''))
    c.drawString(EX, py(287,297), data.get('nationaliteit', ''))
    c.drawString(EX, py(307,317), data.get('fmscrv', ''))
    c.drawString(EX, py(335,345), data.get('adres_buitenland', ''))
    c.drawString(EX, py(358,368), data.get('woonplaats', ''))
    c.drawString(EX, py(382,392), data.get('land', ''))
    c.drawString(EX, py(406,416), data.get('verblijfsadres_curacao', ''))
    c.drawString(EX, py(422,432), data.get('postadres_curacao', ''))
    c.drawString(EX, py(442,452), data.get('telefoon', ''))
    c.drawString(EX, py(462,471), data.get('email', ''))
    c.drawString(EX, py(478,487), data.get('paspoort_nr', ''))
    c.drawString(EX, py(501,511), data.get('plaats_uitgifte', ''))
    c.drawString(EX, py(521,531), data.get('datum_uitgifte', ''))
    c.drawString(400, py(521,531), data.get('geldig_tot', ''))

    gehuwd = data.get('gehuwd', 'nee')
    if gehuwd == 'ja':
        c.drawString(184, py(560,570), "X")
        c.drawString(326, py(560,570), data.get('datum_huwelijk', ''))
    else:
        c.drawString(148, py(560,570), "X")
    c.showPage()

    # ── PÁGINA 3 ─────────────────────────────────────────────────────────────
    partner = data.get('partner_achternaam', '')
    if partner:
        c.drawString(170, py(225,235), partner)
        c.drawString(170, py(245,255), data.get('partner_voornamen', ''))
        c.drawString(170, py(265,274), data.get('partner_fmscrv', ''))
        c.drawString(170, py(284,294), data.get('partner_geboortedatum', ''))
        c.drawString(370, py(284,294), data.get('partner_geboorteland', ''))
        c.drawString(170, py(304,314), data.get('partner_geboorteplaats', ''))
        c.drawString(170, py(324,334), data.get('partner_nationaliteit', ''))
    else:
        c.drawString(78, py(205,215), "X")

    kinderen = data.get('kinderen', [])
    if kinderen:
        kind_rows = [(443,452),(463,472),(482,492),(502,512),(522,532),(542,552)]
        for i, kind in enumerate(kinderen[:6]):
            t, b = kind_rows[i]
            c.setFont("Helvetica", 7)
            c.drawString(78,  py(t,b), kind.get('naam', ''))
            c.drawString(268, py(t,b), kind.get('geboortedatum', ''))
            c.drawString(356, py(t,b), kind.get('geboorteland', ''))
            c.drawString(448, py(t,b), kind.get('nationaliteit', ''))
            c.setFont("Helvetica", 8)
    else:
        c.drawString(78, py(371,381), "X")
    c.showPage()

    # ── PÁGINA 4 ─────────────────────────────────────────────────────────────
    c.drawString(196, py(250,260), data.get('beroep', ''))
    c.showPage()
    c.showPage()
    c.showPage()
    c.save()
    packet.seek(0)
    return packet


def fill_xcg_form_bytes(data, input_path):
    """Genera el PDF y retorna los bytes (para enviar por email o HTTP)."""
    reader = PdfReader(input_path)
    overlay = PdfReader(create_overlay(data))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i < len(overlay.pages):
            page.merge_page(overlay.pages[i])
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def fill_xcg_form(data, input_path, output_path):
    """Genera el PDF y lo guarda en disco."""
    pdf_bytes = fill_xcg_form_bytes(data, input_path)
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)
    print(f"✅ PDF listo: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) == 3:
        with open(sys.argv[1]) as f:
            data = json.load(f)
        fill_xcg_form(data,
            "formulario_xcg_base.pdf",
            sys.argv[2])
