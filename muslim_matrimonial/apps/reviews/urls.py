from django.urls import path

from .views import ReviewDestroyView, ReviewListCreateView

app_name = "reviews"

urlpatterns = [
    path("", ReviewListCreateView.as_view(), name="list-create"),
    path("<uuid:pk>", ReviewDestroyView.as_view(), name="delete"),
]
