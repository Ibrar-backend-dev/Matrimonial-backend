from django.urls import path

from .views import ReportListCreateView

app_name = "reports"

urlpatterns = [path("", ReportListCreateView.as_view(), name="list-create")]
