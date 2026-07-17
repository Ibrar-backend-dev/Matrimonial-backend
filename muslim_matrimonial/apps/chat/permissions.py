from rest_framework.permissions import BasePermission

from apps.matches.models import MatchRequest


class CanAccessAcceptedMatch(BasePermission):
    def has_permission(self, request, view):
        return MatchRequest.objects.filter(
            pk=view.kwargs.get("match_id"),
            status="accepted",
        ).filter(sender=request.user).exists() or MatchRequest.objects.filter(
            pk=view.kwargs.get("match_id"),
            status="accepted",
            receiver=request.user,
        ).exists()
