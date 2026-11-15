from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class QrToken(models.Model):
    """Token assinado de QR: um ativo por sujeito (member|vehicle).

    O payload assinado nunca contém PII — apenas ``v``/``k``/``ti``/``iat``/``exp``;
    nome e time são resolvidos server-side pelo app leitor.

    O XOR member/vehicle e a coerência subject_type↔FK são garantidos em nível
    de banco pelo CheckConstraint ``ck_qr_token_single_subject``; o ``clean()``
    é apenas conveniência para forms/serializers.
    """

    SUBJECT_CHOICES = [("member", "member"), ("vehicle", "vehicle")]
    STATUS_CHOICES = [("active", "active"), ("revoked", "revoked")]

    subject_type = models.CharField(max_length=10, choices=SUBJECT_CHOICES)
    member = models.ForeignKey(
        "registry.Member",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="qr_tokens",
    )
    vehicle = models.ForeignKey(
        "registry.Vehicle",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="qr_tokens",
    )
    token_id = models.UUIDField(unique=True, editable=False)
    payload_json = models.JSONField()
    signature = models.CharField(max_length=96)  # b64u sem padding (86 chars)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active", db_index=True
    )
    issued_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["subject_type", "member", "vehicle"],
                condition=Q(status="active"),
                nulls_distinct=False,
                name="uniq_qr_active_per_subject",
            ),
            models.CheckConstraint(
                condition=Q(member__isnull=False, vehicle__isnull=True)
                | Q(member__isnull=True, vehicle__isnull=False),
                name="ck_qr_token_single_subject",
            ),
        ]

    def clean(self):
        """Valida XOR member/vehicle e coerência com ``subject_type``.

        Conveniência: a garantia forte é o CheckConstraint
        ``ck_qr_token_single_subject`` no banco (aplica-se a qualquer escrita,
        inclusive ``bulk_create``/``raw``).
        """
        has_member = self.member_id is not None
        has_vehicle = self.vehicle_id is not None
        if has_member == has_vehicle:
            raise ValidationError(
                "Exatamente 1 sujeito deve ser preenchido (member XOR vehicle)."
            )
        if self.subject_type == "member" and (not has_member or has_vehicle):
            raise ValidationError(
                "subject_type='member' exige member preenchido e vehicle nulo."
            )
        if self.subject_type == "vehicle" and (not has_vehicle or has_member):
            raise ValidationError(
                "subject_type='vehicle' exige vehicle preenchido e member nulo."
            )
        if self.subject_type not in ("member", "vehicle"):
            raise ValidationError(f"subject_type inválido: {self.subject_type!r}.")

    def __str__(self):
        # Sem PII: identifica o token apenas por tipo + id opaco.
        return f"QrToken[{self.subject_type}/{self.token_id}/{self.status}]"
