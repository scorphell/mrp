"""Renderização de QR (PNG) e credenciais (PDF A4) — segno + ReportLab."""

import base64
from io import BytesIO

import segno
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .qr_service import ensure_active_token, qr_text_for

PAGE_W, PAGE_H = A4
QR_SIZE_PT = 86  # ~3 cm — legível a distância, dentro da leitura do app
_MARGIN = 40
_QR_MARGIN = 10
_TABLE_LEFT = _MARGIN
_TABLE_RIGHT = PAGE_W - _MARGIN
_TABLE_WIDTH = _TABLE_RIGHT - _TABLE_LEFT
_ROW_H = 96
_HEADER_H = 120
_FOOTER_H = 60


def render_qr_png(qr_text: str, *, scale: int = 6, border: int = 2) -> bytes:
    """PNG do QR com ECC nível Q."""
    qr = segno.make(qr_text, error="q")
    buffer = BytesIO()
    qr.save(buffer, kind="png", scale=scale, border=border)
    return buffer.getvalue()


def qr_png_data_uri(qr_text: str, **kwargs) -> str:
    """Data URI (RFC 2397) do PNG, para consumo direto no PWA."""
    image = render_qr_png(qr_text, **kwargs)
    return "data:image/png;base64," + base64.b64encode(image).decode("ascii")


def _draw_header(page, team):
    """Cabeçalho estilo nota fiscal: emitente + dados do documento/equipe."""
    page.setFont("Helvetica-Bold", 14)
    page.setFillColor(colors.black)
    page.drawString(_MARGIN, PAGE_H - _MARGIN - 2, team.name)
    page.setFont("Helvetica", 10)
    page.setFillColor(colors.HexColor("#444444"))
    page.drawString(
        _MARGIN, PAGE_H - _MARGIN - 20, "Mousetrap Racing 2026 — Documento de Credenciamento"
    )

    right = _TABLE_RIGHT
    page.setFont("Helvetica-Bold", 13)
    page.drawRightString(right, PAGE_H - _MARGIN - 4, "CREDENCIAL")
    page.setFont("Helvetica", 9)
    page.setFillColor(colors.HexColor("#555555"))
    doc_number = f"No. DOC 0000{team.pk:04d}"
    page.drawRightString(right, PAGE_H - _MARGIN - 19, doc_number)

    page.setFont("Helvetica", 9)
    page.setFillColor(colors.black)
    base_y = PAGE_H - _MARGIN - 44
    details = [
        f"Curso: {team.course}",
        f"Campus: {team.campus}",
        f"Chassi: {(getattr(team, 'vehicle', None).name if getattr(team, 'vehicle', None) else '—')}",
    ]
    for i, text in enumerate(details):
        page.drawString(_MARGIN, base_y - i * 13, text)

    page.setStrokeColor(colors.HexColor("#999999"))
    page.setLineWidth(0.8)
    page.line(_MARGIN, base_y - 44, _TABLE_RIGHT, base_y - 44)


def _draw_row_header(page, top):
    """Cabeçalho da tabela de itens."""
    page.setFont("Helvetica-Bold", 8)
    page.setFillColor(colors.HexColor("#333333"))
    page.drawString(_TABLE_LEFT + 10, top - 14, "No.")
    page.drawString(_TABLE_LEFT + 40, top - 14, "Identificação")
    page.drawString(_TABLE_RIGHT - 180, top - 14, "Função")
    page.setStrokeColor(colors.HexColor("#999999"))
    page.line(_TABLE_LEFT, top - 22, _TABLE_RIGHT, top - 22)


def _draw_line_row(page, top, number, title, subtitle, tag, tag_color, qr_text):
    """Linha de item da credencial: identificação à esquerda + QR à direita."""
    page.setFillColor(colors.white)
    page.setStrokeColor(colors.HexColor("#bbbbbb"))
    page.setLineWidth(0.5)
    page.rect(_TABLE_LEFT, top - _ROW_H, _TABLE_WIDTH, _ROW_H, stroke=1, fill=0)

    qr_x = _TABLE_RIGHT - _QR_MARGIN - QR_SIZE_PT
    qr_y = top - _ROW_H + (_ROW_H - QR_SIZE_PT) / 2
    page.drawImage(
        ImageReader(BytesIO(render_qr_png(qr_text))),
        qr_x,
        qr_y,
        width=QR_SIZE_PT,
        height=QR_SIZE_PT,
    )

    page.setFont("Helvetica-Bold", 8)
    page.setFillColor(colors.HexColor("#666666"))
    page.drawString(_TABLE_LEFT + 10, top - 42, number)

    page.setFont("Helvetica-Bold", 12)
    page.setFillColor(colors.black)
    page.drawString(_TABLE_LEFT + 40, top - 42, title)

    page.setFont("Helvetica", 9)
    page.setFillColor(colors.HexColor("#555555"))
    page.drawString(_TABLE_LEFT + 40, top - 62, subtitle)

    page.setFont("Helvetica-Bold", 8)
    page.setFillColor(colors.HexColor(tag_color))
    page.drawRightString(_TABLE_RIGHT - _QR_MARGIN - QR_SIZE_PT - 8, top - 42, tag)


def _member_row(page, member, qr_text, number, top):
    tag = "LÍDER" if member.role == "leader" else "PARTICIPANTE"
    tag_color = "#a16207" if member.role == "leader" else "#444444"
    subtitle = f"RA {member.ra}"
    _draw_line_row(page, top, number, member.name, subtitle, tag, tag_color, qr_text)


def _vehicle_row(page, vehicle, qr_text, number, top):
    tag = "CHASSI"
    tag_color = "#155e75"
    subtitle = "Carrinho — inspeção técnica"
    _draw_line_row(page, top, number, vehicle.name, subtitle, tag, tag_color, qr_text)


def render_team_pdf(team) -> bytes:
    """Documento de credenciamento A4 estilo nota fiscal.

    Cabeçalho de documento + uma linha (item) por integrante e pelo chassi,
    cada linha com seu QR à direita. Não imprime e-mail (LGPD).
    """
    buffer = BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    page.setTitle(f"Credencial — {team.name}")
    _draw_header(page, team)

    rows = []
    for member in team.members.all()[:5]:
        token = ensure_active_token("member", member=member)
        rows.append(("member", member, token))
    vehicle = getattr(team, "vehicle", None)
    if vehicle is not None:
        token = ensure_active_token("vehicle", vehicle=vehicle)
        rows.append(("vehicle", vehicle, token))

    table_top = PAGE_H - _MARGIN - _HEADER_H
    _draw_row_header(page, table_top)

    for index, (kind, subject, token) in enumerate(rows):
        card_top = table_top - 22 - index * _ROW_H
        if kind == "member":
            _member_row(page, subject, qr_text_for(token), f"{index + 1:02d}", card_top)
        else:
            _vehicle_row(page, subject, qr_text_for(token), f"{index + 1:02d}", card_top)

    footer_top = table_top - 22 - len(rows) * _ROW_H - 8
    page.setStrokeColor(colors.HexColor("#999999"))
    page.setLineWidth(0.8)
    page.line(_TABLE_LEFT, footer_top, _TABLE_RIGHT, footer_top)

    page.setFont("Helvetica", 9)
    page.setFillColor(colors.black)
    page.drawString(_TABLE_LEFT, footer_top - 18, f"Total de itens: {len(rows)}")
    page.setFont("Helvetica", 8.5)
    page.setFillColor(colors.HexColor("#555555"))
    note = (
        f"Documento de credenciamento — apresente o QR na entrada. "
        f"Data de emissão: {timezone.localdate().isoformat()}"
    )
    page.drawString(_TABLE_LEFT, footer_top - 34, note)
    page.setFont("Helvetica", 7.5)
    page.setFillColor(colors.HexColor("#888888"))
    page.drawString(
        _TABLE_LEFT,
        footer_top - 48,
        "Documento emitido eletronicamente. Não armazena dados além do necessários ao credenciamento.",
    )

    page.showPage()
    page.save()
    return buffer.getvalue()
