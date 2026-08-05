from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardResultsPagination
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
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        queryset = Verification.objects.select_related("user")
        status = self.request.query_params.get("status", "pending")
        selfie_verified = self.request.query_params.get("selfie_verified")
        user_email = self.request.query_params.get("user_email")
        has_doc_url = self.request.query_params.get("has_doc_url")

        if status != "all":
            queryset = queryset.filter(visit_status=status)

        if selfie_verified is not None:
            if selfie_verified.lower() in {"true", "1", "yes"}:
                queryset = queryset.filter(selfie_verified=True)
            elif selfie_verified.lower() in {"false", "0", "no"}:
                queryset = queryset.filter(selfie_verified=False)

        if has_doc_url is not None:
            if has_doc_url.lower() in {"true", "1", "yes"}:
                queryset = queryset.exclude(doc_url__isnull=True)
            elif has_doc_url.lower() in {"false", "0", "no"}:
                queryset = queryset.filter(doc_url__isnull=True)

        if user_email:
            queryset = queryset.filter(user__email__icontains=user_email)

        if status == "pending" and selfie_verified is None and has_doc_url is None and not user_email:
            queryset = queryset.filter(selfie_verified=False).exclude(doc_url__isnull=True)

        return queryset.order_by("-updated_at")


class AdminVerificationUpdateView(generics.UpdateAPIView):
    serializer_class = AdminVerificationSerializer
    permission_classes = [IsAdminRole]
    queryset = Verification.objects.all().select_related("user")

    def perform_update(self, serializer):
        serializer.save(verified_by=self.request.user)
