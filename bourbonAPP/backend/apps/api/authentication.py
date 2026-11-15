"""Autenticação Bearer JWT (Ed25519) para staff (User) e equipes (TeamPrincipal)."""

from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.core.services.jwt_service import JwtError, decode_token
from apps.registry.models import Team


class TeamPrincipal:
    """Sujeito de autenticação de equipe (nunca um User Django).

    User-like o suficiente para o DRF: ``is_authenticated=True``, ``pk``/``id``
    e ``team``. Sem ``is_staff`` de propósito — rotas de staff checam o tipo.
    """

    is_authenticated = True
    is_active = True

    def __init__(self, team):
        self.team = team
        self.pk = team.pk
        self.id = team.pk

    def __str__(self):
        return f"TeamPrincipal({self.pk})"


class BearerJwtAuthentication(BaseAuthentication):
    """Lê ``Authorization: Bearer <jwt>`` e autentica staff ou equipe."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.headers.get("Authorization")
        if not header or not header.startswith("Bearer "):
            return None
        token = header[len("Bearer ") :].strip()

        try:
            claims = decode_token(token)
        except JwtError:
            raise AuthenticationFailed(
                "Token inválido ou expirado.", code="invalid_token"
            ) from None

        if claims.get("typ") == "staff":
            user = (
                get_user_model()
                .objects.filter(pk=claims.get("uid"), is_active=True)
                .first()
            )
            if user is None:
                raise AuthenticationFailed(
                    "Token inválido ou expirado.", code="invalid_token"
                )
            # Usuário não-staff autentica (is_staff fake→403 via IsStaff);
            # checagem explícita evita confundir com token inválido.
            return (user, claims)

        # Token de equipe vale até expirar mesmo com a equipe inativa (E.4):
        # o que bloqueia fluxos após revogação é o status no domínio
        # (login, issue, verify de QR revogado), não a autenticação aqui.
        team = Team.objects.filter(
            pk=claims.get("tid"), registered_at__isnull=False
        ).first()
        if team is None:
            raise AuthenticationFailed(
                "Token inválido ou expirado.", code="invalid_token"
            )
        return (TeamPrincipal(team), claims)

    def authenticate_header(self, request):
        return "Bearer"
