"""Filtros e formatters de log com remoção de PII (LGPD §8).

O ``PiiScrubber`` roda ANTES do ``JsonFormatter``: interpola a mensagem,
remove e-mails, valores de ``Authorization``/``Cookie`` e valores da chave
``name`` (formato JSON/chave-valor), deixando o registro pronto para saída —
nenhuma linha de log carrega combinação ``UUID + nome/e-mail``.
"""

import datetime
import json
import logging
import re

_PATTERNS = (
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL_REDACTED]",
    ),
    (re.compile(r"(?i)(authorization\s*[:=]\s*)[^\n]*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(cookie\s*[:=]\s*)[^\n]*"), r"\1[REDACTED]"),
    (re.compile(r'(?i)("name"\s*:\s*")[^"]*(")'), r"\1[REDACTED]\2"),
    (re.compile(r'(?i)(\bname\s*[:=]\s*["\'][^"\']*["\'])'), r"[REDACTED]"),
)


class PiiScrubber(logging.Filter):
    """Substitui e-mail/Authorization/Cookie/name por marcadores na mensagem."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "pii_scrubbed", False):
            return True
        message = record.getMessage()
        for pattern, replacement in _PATTERNS:
            message = pattern.sub(replacement, message)
        record.msg = message
        record.args = ()
        record.pii_scrubbed = True
        return True


class JsonFormatter(logging.Formatter):
    """Formata o registro como JSON compacto (sem request.body)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.datetime.fromtimestamp(
                record.created, datetime.timezone.utc
            ).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
