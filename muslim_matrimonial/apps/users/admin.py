from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("-created_at",)
    list_display = ("phone", "email", "role", "status", "otp_verified", "is_staff")
    search_fields = ("phone", "email")
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("Account", {"fields": ("email", "role", "status", "otp_verified")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "created_at")}),
    )
    readonly_fields = ("created_at", "last_login")
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "password1", "password2", "is_staff")}),
    )
