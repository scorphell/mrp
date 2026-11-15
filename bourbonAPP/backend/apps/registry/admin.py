from django.contrib import admin

from .models import EventSession, Member, Team, Vehicle


class MemberInline(admin.TabularInline):
    model = Member
    extra = 0


@admin.register(EventSession)
class EventSessionAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "date", "status")
    list_filter = ("kind", "status")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "course", "campus", "status", "registration_code")
    list_filter = ("status", "campus")
    search_fields = ("name", "course")
    readonly_fields = ("registration_code",)
    inlines = [MemberInline]


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "role", "ra", "email", "consent_at")
    list_filter = ("role", "team")
    search_fields = ("name", "ra", "email")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "conformity_status", "conformity_checked_at")
    list_filter = ("conformity_status",)
    search_fields = ("name", "team__name")
