from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Allow access when the object belongs to the authenticated user."""

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        if owner is None:
            owner = getattr(getattr(obj, "profile", None), "user", None)
        return request.user.is_authenticated and owner == request.user


class IsAdminOrOwner(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False
        if request.user.is_staff or getattr(request.user, "role", None) == "admin":
            return True
        owner = getattr(obj, "user", None)
        if owner is None:
            owner = getattr(getattr(obj, "profile", None), "user", None)
        return owner == request.user


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user.is_authenticated
            and (request.user.is_staff or request.user.role == "admin")
        )
