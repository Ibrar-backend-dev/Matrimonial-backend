from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles.models import Profile
from apps.profiles.serializers import ProfileSerializer
from apps.users.models import User
from core.pagination import StandardResultsPagination
from core.throttles import AuthenticatedUserThrottle

from .models import MatchRequest
from .serializers import MatchFilterSerializer, MatchRequestSerializer, MatchResponseSerializer
from .services import eligible_profiles, get_daily_suggestions, is_profile_visible_to


class SuggestionListView(generics.GenericAPIView):
    serializer_class = ProfileSerializer
    throttle_classes = [AuthenticatedUserThrottle]
    throttle_scope = "match"

    def get(self, request):
        suggestions = get_daily_suggestions(request.user)
        return Response(ProfileSerializer(suggestions, many=True, context={"request": request}).data)


class MatchFilterView(generics.GenericAPIView):
    serializer_class = MatchFilterSerializer
    throttle_classes = [AuthenticatedUserThrottle]
    throttle_scope = "match"

    def post(self, request):
        filters = MatchFilterSerializer(data=request.data, context={"request": request})
        filters.is_valid(raise_exception=True)
        queryset = eligible_profiles(request.user, filters.validated_data)
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = ProfileSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class MatchRequestCreateView(generics.GenericAPIView):
    serializer_class = MatchRequestSerializer
    throttle_classes = [AuthenticatedUserThrottle]
    throttle_scope = "match"

    def post(self, request, user_id):
        receiver = get_object_or_404(User, pk=user_id, is_active=True, status="active")
        if receiver == request.user:
            raise ValidationError("A user cannot send a match request to themselves.")
        try:
            receiver_profile = receiver.profile
        except Profile.DoesNotExist:
            raise ValidationError("The selected user does not have a profile.")
        if not is_profile_visible_to(request.user, receiver_profile):
            raise ValidationError("This user does not satisfy both users' interest filters.")
        try:
            match = MatchRequest.objects.create(sender=request.user, receiver=receiver)
        except IntegrityError:
            raise ValidationError("A match request has already been sent to this user.")
        return Response(MatchRequestSerializer(match).data, status=status.HTTP_201_CREATED)


class MatchRespondView(generics.GenericAPIView):
    serializer_class = MatchResponseSerializer
    throttle_classes = [AuthenticatedUserThrottle]
    throttle_scope = "match"

    @transaction.atomic
    def patch(self, request, request_id):
        response = MatchResponseSerializer(data=request.data)
        response.is_valid(raise_exception=True)
        match = get_object_or_404(MatchRequest.objects.select_for_update(), pk=request_id, receiver=request.user)
        if match.status != "pending":
            raise ValidationError("This match request has already been answered.")
        match.status = response.validated_data["status"]
        match.responded_at = timezone.now()
        match.save(update_fields=["status", "responded_at"])
        return Response(MatchRequestSerializer(match).data)
