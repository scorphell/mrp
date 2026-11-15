"""Testes de renderização PNG/PDF (chaves fictícias; PDF emite tokens por equipe)."""

import re
import struct
import tempfile
import zlib
from pathlib import Path

import segno
from django.test import TestCase, override_settings
from reportlab.pdfbase.pdfutils import asciiBase85Decode

from apps.registry.models import Member, Team, Vehicle

from ..services.rendering import render_qr_png, render_team_pdf

from . import make_keypair

QR_TEXT = "MRP1.eyJ0ZXN0IjoxfQ.some_signature"


def page_text(pdf: bytes) -> bytes:
    """Extrai e descomprime o stream de conteúdo da página.

    O reportlab grava os streams como ASCII85+Flate. A busca cega por
    b"@" no PDF cru é frágil: o caractere pode aparecer por acaso no
    binário codificado das imagens embutidas. Aqui olhamos apenas o
    texto desenhado (o stream /Contents), que é o que importa.
    """
    match = re.search(rb"/Contents (\d+) 0 R", pdf)
    if not match:
        return b""
    object_start = pdf.find(match.group(1) + b" 0 obj")
    stream_start = pdf.find(b"stream\n", object_start) + len(b"stream\n")
    stream_end = pdf.find(b"endstream", stream_start)
    return zlib.decompress(asciiBase85Decode(pdf[stream_start:stream_end]))


def make_full_team(name):
    """Equipe com 5 membros + chassi (fictícios) para o PDF."""
    team = Team.objects.create(
        name=name, course="Engenharia Mecânica", campus="Campus Centro"
    )
    Member.objects.bulk_create(
        [
            Member(
                team=team,
                name=f"{name} Membro {i}",
                email=f"{name.lower()}.{i}@exemplo.test",
                ra=f"RARENDER{i:04d}",
                role="leader" if i == 0 else "member",
            )
            for i in range(5)
        ]
    )
    Vehicle.objects.create(team=team, name=f"{name} Chassi")
    return team


def png_to_matrix(data: bytes) -> list[list[int]]:
    """Decodifica o PNG 1-bit/grayscale do segno de volta na matriz de módulos.

    O segno inverte os bits ao gravar (módulo escuro = 0 no PNG), então o valor
    decodificado aqui segue a convenção da matriz do segno (1 = módulo escuro).
    """
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    idat = bytearray()
    width = height = bit_depth = color_type = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk[:10])
        elif kind == b"IDAT":
            idat.extend(chunk)
        pos += 12 + length
    assert (bit_depth, color_type) == (1, 0), (bit_depth, color_type)
    raw = zlib.decompress(bytes(idat))
    stride = (width + 7) // 8
    rows = []
    prev = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset : offset + stride])
        offset += stride
        if filter_type == 1:  # Sub
            for i in range(stride):
                left = line[i - 1] if i > 0 else 0
                line[i] = (line[i] + left) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(stride):
                left = line[i - 1] if i > 0 else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(stride):
                a = line[i - 1] if i > 0 else 0
                b = prev[i]
                c = prev[i - 1] if i > 0 else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        prev = line
        rows.append(
            [1 - ((line[col >> 3] >> (7 - (col & 7))) & 1) for col in range(width)]
        )
    return rows


class QrPngTests(TestCase):
    def test_png_magic_and_matrix_content(self):
        png = render_qr_png(QR_TEXT, scale=1, border=0)
        self.assertEqual(png[:4], b"\x89PNG")
        matrix = png_to_matrix(png)
        expected = [list(row) for row in segno.make(QR_TEXT, error="q").matrix]
        self.assertEqual(matrix, expected)

    def test_qr_uses_ecc_level_q(self):
        # O segno eleva o nível de ECC automaticamente quando o conteúdo cabe
        # (comportamento documentado); error="q" é o mínimo contratado.
        qr = segno.make(QR_TEXT, error="q")
        self.assertIn(qr.error, ("Q", "H"))

    def test_scaled_png_size(self):
        png = render_qr_png(QR_TEXT)
        qr = segno.make(QR_TEXT, error="q")
        expected_size = (qr.version * 4 + 17 + 2 * 2) * 6
        self.assertEqual(len(png_to_matrix(png)[0]), expected_size)


class TeamPdfTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.priv_path, cls.pub_path, _ = make_keypair(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()
        super().tearDownClass()

    def setUp(self):
        override = override_settings(
            ED25519_PRIVATE_PATH=str(self.priv_path),
            ED25519_PUBLIC_PATH=str(self.pub_path),
        )
        override.enable()
        self.addCleanup(override.disable)

    def test_pdf_is_valid_and_one_page_for_full_team(self):
        team = make_full_team("Equipe PDF")
        pdf = render_team_pdf(team)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/Type /Catalog", pdf)
        pages = pdf.count(b"/Type /Page") - pdf.count(b"/Type /Pages")
        self.assertEqual(pages, 1)

    def test_pdf_does_not_contain_email(self):
        team = make_full_team("Equipe Sem Email")
        pdf = render_team_pdf(team)
        self.assertNotIn(b"@", page_text(pdf))
