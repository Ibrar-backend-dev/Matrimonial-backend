from django.urls import path

from .views import (
    ForgotPasswordView,
    LoginVerifyOTPView,
    LoginView,
    LogoutView,
    RefreshTokenView,
    RegisterView,
    UserDeleteView,
    VerifyOTPView,
)

app_name = "users"

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("verify-otp", VerifyOTPView.as_view(), name="verify-otp"),
    path("login", LoginView.as_view(), name="login"),
    path("login/verify-otp", LoginVerifyOTPView.as_view(), name="login-verify-otp"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("refresh-token", RefreshTokenView.as_view(), name="refresh-token"),
    path("forgot-password", ForgotPasswordView.as_view(), name="forgot-password"),
    path("delete", UserDeleteView.as_view(), name="delete"),
]
