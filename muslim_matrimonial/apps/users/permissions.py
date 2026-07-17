from rest_framework.permissions import BasePermission


class IsActiveVerifiedUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user.is_authenticated
            and user.is_active
            and user.otp_verified
            and user.status == "active"
        )
