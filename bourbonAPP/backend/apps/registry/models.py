import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class EventSession(models.Model):
    """Sessão de evento (validação ou final) na qual check-ins acontecem."""

    KIND_CHOICES = [("validation", "validation"), ("final", "final")]
    STATUS_CHOICES = [("planned", "planned"), ("open", "open"), ("closed", "closed")]

    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "name"]

    def __str__(self):
        return f"{self.name} ({self.date})"


class Team(models.Model):
    """Equipe inscrita (3–5 membros) e seu código de inscrição (QR/portal)."""

    STATUS_CHOICES = [("active", "active"), ("inactive", "inactive")]

    name = models.CharField(max_length=120, unique=True)
    course = models.CharField(max_length=120)
    campus = models.CharField(max_length=120)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    registration_code = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False
    )
    registered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class TeamAuth(models.Model):
    """Credencial de login do portal: hash PBKDF2 da senha + OneToOne com Team."""

    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name="auth")
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"TeamAuth[{self.team_id}]"


class Member(models.Model):
    """Participante de uma equipe; dados pessoais minimizados (LGPD)."""

    ROLE_CHOICES = [("leader", "leader"), ("member", "member")]

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    ra = models.CharField(max_length=30, unique=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="member")
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["team", "role", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "role"],
                condition=Q(role="leader"),
                name="uniq_leader_per_team",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.team_id})"

    def clean(self):
        """Valida a regra de equipe: líder único e faixa de 3–5 membros.

        A faixa conta os membros já persistidos; no insert o próprio registro
        ainda não existe no banco (por isso +1). No update ``count()`` já
        inclui o próprio, e o líder atual é excluído da consulta.
        """
        super().clean()
        if self.team_id is None:
            raise ValidationError({"team": "O membro precisa de uma equipe."})
        if (
            self.role == "leader"
            and self.team.members.filter(role="leader").exclude(pk=self.pk).exists()
        ):
            raise ValidationError({"role": "A equipe já possui um líder."})
        total = self.team.members.count() + (0 if self.pk else 1)
        if not 3 <= total <= 5:
            raise ValidationError({"team": "A equipe deve ter entre 3 e 5 membros."})

    def save(self, *args, **kwargs):
        """Garante validação em todo salvamento individual.

        ``bulk_create`` e ``QuerySet.update`` NÃO passam por aqui de propósito:
        o portal de cadastro (M3) e seeds criam times inteiros em lote, quando
        a validação 3–5 por registro individual não faz sentido.
        """
        self.full_clean()
        super().save(*args, **kwargs)


class Vehicle(models.Model):
    """Chassi da equipe (OneToOne); estado de conformidade denormalizado."""

    CONFORMITY_CHOICES = [("pass", "pass"), ("fail", "fail")]

    team = models.OneToOneField(Team, on_delete=models.CASCADE, related_name="vehicle")
    name = models.CharField(max_length=120)
    conformity_status = models.CharField(
        max_length=10, choices=CONFORMITY_CHOICES, null=True, blank=True
    )
    conformity_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.team_id})"
