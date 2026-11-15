"""Permissões da API: staff (User Django), equipe e membro da equipe."""

from rest_framework.permissions import BasePermission

from .authentication import TeamPrincipal


class IsStaff(BasePermission):
    """Apenas usuários Django com ``is_staff=True`` (capataz/fiscal)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user is not None
            and user.is_authenticated
            and getattr(user, "is_staff", False)
        )


class IsTeam(BasePermission):
    """Apenas instâncias de ``TeamPrincipal`` (time autenticado)."""

    def has_permission(self, request, view):
        return isinstance(request.user, TeamPrincipal)


class IsTeamMember(BasePermission):
    """Time autenticado cujo pk bate com o time do sujeito da URL."""

    def has_permission(self, request, view):
        if not isinstance(request.user, TeamPrincipal):
            return False
        subject_type = view.kwargs.get("subject_type")
        subject_pk = view.kwargs.get("pk")
        return _subject_team_id(subject_type, subject_pk) == request.user.team.pk


def _subject_team_id(subject_type, subject_pk):
    """Time dono do sujeito (member|vehicle) da URL, ou None."""
    from apps.registry.models import Member, Vehicle

    if subject_type == "member":
        return (
            Member.objects.filter(pk=subject_pk)
            .values_list("team_id", flat=True)
            .first()
        )
    if subject_type == "vehicle":
        return (
            Vehicle.objects.filter(pk=subject_pk)
            .values_list("team_id", flat=True)
            .first()
        )
    return None
