from django.contrib import admin

from .models import Photo, Preference, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "gender", "city", "country", "marital_status", "created_at")
    list_filter = ("gender", "city", "country", "marital_status", "photo_privacy_level")
    search_fields = ("name", "user__phone", "city", "country", "education")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("profile", "id", "is_primary", "privacy_level")
    list_filter = ("privacy_level", "is_primary")
    search_fields = ("profile__name",)


@admin.register(Preference)
class PreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "interested_in", "age_range_min", "age_range_max")
    list_filter = ("interested_in", "sect_pref")
    search_fields = ("user__phone",)
