from django.urls import path

from .views import (
    ForgotPasswordView,
    LoginView,
    LogoutView,
    RefreshTokenView,
    RegisterView,
    ResendOTPView,
    UserDeleteView,
    VerifyOTPView,
)

app_name = "users"

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("verify-otp", VerifyOTPView.as_view(), name="verify-otp"),
    path("resend-otp", ResendOTPView.as_view(), name="resend-otp"),
    path("login", LoginView.as_view(), name="login"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("refresh-token", RefreshTokenView.as_view(), name="refresh-token"),
    path("forgot-password", ForgotPasswordView.as_view(), name="forgot-password"),
    path("delete", UserDeleteView.as_view(), name="delete"),
]
