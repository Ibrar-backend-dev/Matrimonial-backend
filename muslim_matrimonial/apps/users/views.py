import secrets

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from core.throttles import AnonIPThrottle, AuthenticatedUserThrottle

from .models import User
from .serializers import (
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    OTPSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .tasks import issue_otp, otp_cache_key


class OTPEmailRateThrottle(SimpleRateThrottle):
    scope = "otp_email"

    def get_cache_key(self, request, view):
        email = str(request.data.get("email", "")).lower().strip()
        if not email:
            return None
        return self.cache_format % {"scope": self.scope, "ident": email}


class RegisterView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_classes = [ScopedRateThrottle, OTPEmailRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        otp = issue_otp(user.email)
        data = {"user": UserSerializer(user).data, "detail": "OTP sent to email."}
        if settings.DEBUG:
            data["otp"] = otp
        return Response(data, status=status.HTTP_201_CREATED)


class VerifyOTPView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = OTPSerializer
    throttle_classes = [AnonIPThrottle, AuthenticatedUserThrottle]
    throttle_scope = "auth_authenticated"

    def post(self, request):
        serializer = OTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        expected = cache.get(otp_cache_key(email, "verify"))
        if expected is None or not secrets.compare_digest(str(expected), serializer.validated_data["otp"]):
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(User, email=email)
        user.otp_verified = True
        user.is_active = True
        user.status = "active"
        user.save(update_fields=["otp_verified", "is_active", "status"])
        cache.delete(otp_cache_key(email, "verify"))
        return Response({"detail": "Email verified."})


class LoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            return Response({"detail": "Invalid or expired refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Logged out."})


class ForgotPasswordView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = ForgotPasswordSerializer
    throttle_classes = [ScopedRateThrottle, OTPEmailRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = get_object_or_404(User, email=email, status="active")
        if "otp" not in serializer.validated_data:
            otp = issue_otp(email, "password-reset")
            data = {"detail": "Password reset OTP sent."}
            if settings.DEBUG:
                data["otp"] = otp
            return Response(data)

        expected = cache.get(otp_cache_key(email, "password-reset"))
        supplied = serializer.validated_data["otp"]
        if expected is None or not secrets.compare_digest(str(expected), supplied):
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        cache.delete(otp_cache_key(email, "password-reset"))
        return Response({"detail": "Password updated."})


class UserDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def perform_destroy(self, instance):
        instance.soft_delete()


RefreshTokenView = TokenRefreshView
