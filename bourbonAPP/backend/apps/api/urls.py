"""Rotas da API v1 (base incluída em /api/v1/)."""

from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health_view, name="health"),
    path("auth/staff/login", views.staff_login_view, name="staff-login"),
    path("sessions", views.session_list_view, name="session-list"),
    path("teams/register", views.team_register_view, name="team-register"),
    path("teams/login", views.team_login_view, name="team-login"),
    path("teams/me", views.team_me_view, name="team-me"),
    path("teams/me/export", views.team_export_view, name="team-export"),
    path(
        "teams/me/consent/revoke",
        views.team_consent_revoke_view,
        name="team-consent-revoke",
    ),
    path(
        "credentials/issue/<str:subject_type>/<str:pk>",
        views.credential_issue_view,
        name="credential-issue",
    ),
    path(
        "credentials/team/<int:team_id>/pdf",
        views.team_pdf_view,
        name="team-pdf",
    ),
    path("checkin/verify", views.checkin_verify_view, name="checkin-verify"),
    path("checkin/presence", views.checkin_presence_view, name="checkin-presence"),
    path(
        "checkin/conformity",
        views.checkin_conformity_view,
        name="checkin-conformity",
    ),
]
