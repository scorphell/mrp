from django.contrib import admin

from .models import QrToken


@admin.register(QrToken)
class QrTokenAdmin(admin.ModelAdmin):
    list_display = ("token_id", "subject_type", "status", "issued_at")
    list_filter = ("subject_type", "status")
    readonly_fields = (
        "token_id",
        "issued_at",
        "revoked_at",
    )
