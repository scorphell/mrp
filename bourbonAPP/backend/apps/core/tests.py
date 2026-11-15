import logging

from django.test import SimpleTestCase

from .logging import PiiScrubber


def _scrub(message, args=()):
    record = logging.LogRecord("test", logging.INFO, __file__, 1, message, args, None)
    PiiScrubber().filter(record)
    return record.getMessage()


class PiiScrubberTest(SimpleTestCase):
    def test_scrubs_email(self):
        out = _scrub("participante ana@example.com registrado")
        self.assertNotIn("ana@example.com", out)
        self.assertIn("[EMAIL_REDACTED]", out)

    def test_scrubs_authorization_header(self):
        out = _scrub("falha auth para token Authorization: Bearer abc.def.ghi")
        self.assertNotIn("abc.def.ghi", out)
        self.assertIn("[REDACTED]", out)

    def test_scrubs_cookie_header(self):
        out = _scrub("request invalido Cookie: sessionid=deadbeef1234")
        self.assertNotIn("deadbeef1234", out)
        self.assertIn("[REDACTED]", out)

    def test_scrubs_name_in_json(self):
        out = _scrub('{"action": "checkin.presence", "name": "Maria Silva"}')
        self.assertNotIn("Maria Silva", out)

    def test_scrubs_formatted_arguments(self):
        out = _scrub("duplicado %s", ("ana@example.com",))
        self.assertNotIn("ana@example.com", out)

    def test_percent_literal_is_safe(self):
        out = _scrub("progresso 100% ok")
        self.assertIn("100%", out)
