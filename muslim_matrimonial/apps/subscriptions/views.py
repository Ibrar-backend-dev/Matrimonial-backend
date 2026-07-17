from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminRole

from .models import Subscription
from .serializers import PaymentStatusSerializer, SubscriptionSerializer


class SubscriptionListCreateView(generics.ListCreateAPIView):
    serializer_class = SubscriptionSerializer

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user).order_by("-start_date")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CurrentSubscriptionView(generics.GenericAPIView):
    serializer_class = SubscriptionSerializer

    def get(self, request):
        subscription = Subscription.objects.filter(user=request.user, payment_status="active").order_by("-start_date").first()
        return Response(SubscriptionSerializer(subscription).data if subscription else None)


class PaymentStatusUpdateView(generics.GenericAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = PaymentStatusSerializer

    def patch(self, request, pk):
        subscription = get_object_or_404(Subscription, pk=pk)
        serializer = PaymentStatusSerializer(subscription, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
