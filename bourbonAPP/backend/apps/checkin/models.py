import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class CheckIn(models.Model):
    """Registro de presença idempotente de um sujeito em uma sessão.

    A unicidade é por ``(session, subject_type, subject)``: com
    ``nulls_distinct=False`` (PG 15+/Django 5), NULLs são tratados como iguais,
    então re-leituras do mesmo QR na mesma sessão violam a constraint em vez de
    duplicar linha. O app leitor converte a violação em re-scan (update de
    ``last_seen_at`` via ``auto_now``).
    """

    SUBJECT_CHOICES = [("member", "member"), ("vehicle", "vehicle")]

    session = models.ForeignKey(
        "registry.EventSession", on_delete=models.PROTECT, related_name="checkins"
    )
    subject_type = models.CharField(max_length=10, choices=SUBJECT_CHOICES)
    member = models.ForeignKey(
        "registry.Member",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkins",
    )
    vehicle = models.ForeignKey(
        "registry.Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkins",
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="checkin_records",
    )
    last_seen_at = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "subject_type", "member", "vehicle"],
                condition=Q(member__isnull=False) | Q(vehicle__isnull=False),
                nulls_distinct=False,
                name="uniq_checkin_subject_per_session",
            )
        ]

    def __str__(self):
        subject = self.member_id or self.vehicle_id
        return f"CheckIn[{self.session_id}/{self.subject_type}/{subject}]"


class ConformityCheck(models.Model):
    """Checklist manual de conformidade técnica do veículo (histórico auditável)."""

    RESULT_CHOICES = [("pass", "pass"), ("fail", "fail")]

    vehicle = models.ForeignKey(
        "registry.Vehicle", on_delete=models.PROTECT, related_name="conformity_checks"
    )
    session = models.ForeignKey(
        "registry.EventSession",
        on_delete=models.PROTECT,
        related_name="conformity_checks",
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="conformity_checks",
    )
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    items = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default="")
    checked_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-checked_at"]

    def __str__(self):
        return f"{self.vehicle_id}/{self.session_id}: {self.result}"
