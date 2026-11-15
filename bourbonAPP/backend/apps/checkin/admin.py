from django.contrib import admin

from .models import CheckIn, ConformityCheck


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = (
        "session",
        "subject_type",
        "member_id",
        "vehicle_id",
        "staff",
        "last_seen_at",
    )
    list_filter = ("session", "subject_type")
    readonly_fields = (
        "session",
        "subject_type",
        "member",
        "vehicle",
        "staff",
        "last_seen_at",
        "uuid",
        "created_at",
    )


@admin.register(ConformityCheck)
class ConformityCheckAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "session", "result", "staff", "checked_at")
    list_filter = ("result", "session")
    readonly_fields = (
        "vehicle",
        "session",
        "staff",
        "result",
        "items",
        "notes",
        "checked_at",
        "created_at",
    )
