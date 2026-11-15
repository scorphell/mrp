from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Trilha de auditoria raspada (LGPD): nunca guarda dados pessoais.

    ``meta`` é um JSON livre, mas por política NÃO pode conter nome, e-mail ou
    RA de participante — apenas ids opacos, UUIDs e flags. O IP do requisitante
    entra apenas como SHA-256 com salt (``ip_hash``).
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    actor_team = models.ForeignKey(
        "registry.Team",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=64)
    target_type = models.CharField(max_length=40, null=True, blank=True)
    target_id = models.CharField(max_length=40, null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)
    ip_hash = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self):
        return f"AuditLog[{self.action} @ {self.created_at.isoformat()}]"
