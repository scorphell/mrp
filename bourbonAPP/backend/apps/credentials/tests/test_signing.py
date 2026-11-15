"""Testes de criptografia pura (signing.py) — sem ORM e sem chaves reais."""

import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from apps.credentials.services import signing
from apps.credentials.services.qr_service import verify_qr

from . import make_keypair

PAYLOAD = {
    "v": 1,
    "k": "m",
    "ti": "0f8fad5b-d9cb-469f-a165-70867728950e",
    "iat": 1_752_000_000,
    "exp": 1_772_000_000,
}


class SigningTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls.priv_path, cls.pub_path, cls.priv = make_keypair(Path(cls._tmp.name))
        cls.pub = cls.priv.public_key()
        _, _, cls.other_priv = make_keypair(Path(cls._tmp.name) / "other")
        cls.other_pub = cls.other_priv.public_key()

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

    def test_roundtrip_build_parse(self):
        raw, b64 = signing.sign_payload(PAYLOAD, key=self.priv)
        qr_text = signing.build_qr_text(PAYLOAD, b64)
        payload, signature = signing.parse_qr_text(qr_text)
        self.assertEqual(payload, PAYLOAD)
        self.assertEqual(signature, raw)

    def test_qr_text_shape_matches_regex(self):
        raw, b64 = signing.sign_payload(PAYLOAD, key=self.priv)
        qr_text = signing.build_qr_text(PAYLOAD, b64)
        self.assertRegex(qr_text, r"^MRP1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
        self.assertTrue(qr_text.startswith("MRP1."))
        _, payload_b64, signature_b64 = qr_text.split(".")
        self.assertEqual(
            signing.b64u_decode(payload_b64), signing.canonical_json(PAYLOAD)
        )
        self.assertEqual(signature_b64, b64)

    def test_signature_is_64_bytes_86_chars_b64u(self):
        raw, b64 = signing.sign_payload(PAYLOAD, key=self.priv)
        self.assertEqual(len(raw), 64)
        self.assertEqual(len(b64), 86)
        self.assertNotIn("=", b64)

    def test_tampered_payload_rejected(self):
        raw, b64 = signing.sign_payload(PAYLOAD, key=self.priv)
        tampered = {**PAYLOAD, "exp": PAYLOAD["exp"] + 1}
        self.assertFalse(signing.verify_signature(tampered, raw, pub=self.pub))
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(signing.build_qr_text(tampered, b64))
        self.assertEqual(ctx.exception.reason, "signature")

    def test_tampered_signature_rejected(self):
        raw, b64 = signing.sign_payload(PAYLOAD, key=self.priv)
        qr_text = signing.build_qr_text(PAYLOAD, signing.b64u_encode(b"\x01" * 64))
        payload, signature = signing.parse_qr_text(qr_text)
        self.assertNotEqual(signature, raw)
        self.assertFalse(signing.verify_signature(payload, signature, pub=self.pub))
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(qr_text)
        self.assertEqual(ctx.exception.reason, "signature")

    def test_signature_from_other_key_rejected(self):
        raw, b64 = signing.sign_payload(PAYLOAD, key=self.other_priv)
        self.assertFalse(signing.verify_signature(PAYLOAD, raw, pub=self.pub))
        with self.assertRaises(signing.InvalidQrError) as ctx:
            verify_qr(signing.build_qr_text(PAYLOAD, b64))
        self.assertEqual(ctx.exception.reason, "signature")

    def test_malformed_formats_rejected(self):
        cases = [
            "XRP1.abc.def",  # prefixo errado
            "mrp1.abc.def",  # prefixo minúsculo
            "MRP1.a+b.c",  # caractere inválido no payload
            "MRP1.abc",  # segmento faltando
            "MRP1.abc.def.gh",  # segmento a mais
            "MRP1..def",  # payload vazio
            "MRP1.abc.",  # assinatura vazia
            " MRP1.abc.def",  # espaço à esquerda
            "",
            "MRP1.abc.de+f",  # caractere inválido na assinatura
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(signing.InvalidQrError) as ctx:
                    signing.parse_qr_text(case)
                self.assertEqual(ctx.exception.reason, "format")

    def test_b64u_decode_rejects_invalid_charset(self):
        with self.assertRaises(signing.InvalidQrError) as ctx:
            signing.b64u_decode("ab/c")
        self.assertEqual(ctx.exception.reason, "format")

    def test_canonical_json_is_sorted_and_compact(self):
        payload = {"b": 2, "a": 1}
        self.assertEqual(signing.canonical_json(payload), b'{"a":1,"b":2}')

    def test_key_missing_raises(self):
        with self.assertRaises(signing.Ed25519KeyMissingError):
            signing.load_private_key(self._tmp.name + "/nao-existe.pem")
        with self.assertRaises(signing.Ed25519KeyMissingError):
            signing.load_public_key(self._tmp.name + "/nao-existe.pem")
