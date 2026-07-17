from django.urls import path

from .views import MessageHistoryView

app_name = "chat"

urlpatterns = [path("<uuid:match_id>/history", MessageHistoryView.as_view(), name="history")]
