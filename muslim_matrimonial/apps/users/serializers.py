from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "role", "status", "otp_verified", "created_at")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ("email", "password")

    def create(self, validated_data):
        return User.objects.create_user(is_active=False, **validated_data)


class OTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(
        min_length=6, max_length=6, validators=[RegexValidator(r"^\d{6}$", "OTP must be a 6-digit code.")]
    )


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user = User.objects.get(email=attrs["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.check_password(attrs["password"]):
            raise serializers.ValidationError("Invalid email or password.")
        if not user.otp_verified or not user.is_active or user.status != "active":
            raise serializers.ValidationError("This account is not active and verified.")
        attrs["user"] = user
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6, required=False)
    new_password = serializers.CharField(write_only=True, required=False)

    def validate(self, attrs):
        otp_supplied = "otp" in attrs
        password_supplied = "new_password" in attrs
        if otp_supplied != password_supplied:
            raise serializers.ValidationError("otp and new_password must be supplied together.")
        if password_supplied:
            validate_password(attrs["new_password"])
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
