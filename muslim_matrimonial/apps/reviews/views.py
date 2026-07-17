from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from core.permissions import IsAdminRole

from .models import Review
from .serializers import ReviewSerializer


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer

    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else [IsAuthenticated()]

    def get_queryset(self):
        return Review.objects.filter(is_public=True).select_related("user").order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewDestroyView(generics.DestroyAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAdminRole]
