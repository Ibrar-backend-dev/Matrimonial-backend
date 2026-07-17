from django.contrib import admin

from .models import Photo, Preference, Profile

admin.site.register(Profile)
admin.site.register(Photo)
admin.site.register(Preference)
