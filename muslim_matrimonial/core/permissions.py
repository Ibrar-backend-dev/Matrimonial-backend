from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Allow access when the object belongs to the authenticated user."""

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", obj)
        return request.user.is_authenticated and owner == request.user


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and (request.user.is_staff or request.user.role == "admin")
        )
