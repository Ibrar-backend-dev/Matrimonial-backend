from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdminRole

from .models import Verification
from .serializers import AdminVerificationSerializer, VerificationSerializer


class VerificationSubmitView(generics.GenericAPIView):
    serializer_class = VerificationSerializer

    def post(self, request):
        verification = Verification.objects.filter(user=request.user).first()
        serializer = VerificationSerializer(verification, data=request.data, partial=bool(verification))
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, phone_verified=request.user.otp_verified)
        return Response(serializer.data, status=status.HTTP_200_OK if verification else status.HTTP_201_CREATED)


class PendingVerificationListView(generics.ListAPIView):
    serializer_class = AdminVerificationSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return Verification.objects.filter(selfie_verified=False).exclude(doc_url__isnull=True).select_related("user")
