from rest_framework import generics

from .models import Report
from .serializers import ReportSerializer


class ReportListCreateView(generics.ListCreateAPIView):
    serializer_class = ReportSerializer

    def get_queryset(self):
        return Report.objects.filter(reporter=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)
