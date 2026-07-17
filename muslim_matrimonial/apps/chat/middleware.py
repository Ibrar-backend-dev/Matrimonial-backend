from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def get_user(validated_token):
    user_id = validated_token[api_settings.USER_ID_CLAIM]
    try:
        return get_user_model().objects.get(**{api_settings.USER_ID_FIELD: user_id}, is_active=True)
    except get_user_model().DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = query.get("token", [None])[0]
        if token:
            try:
                scope["user"] = await get_user(AccessToken(token))
            except Exception:
                scope["user"] = AnonymousUser()
        return await self.app(scope, receive, send)
