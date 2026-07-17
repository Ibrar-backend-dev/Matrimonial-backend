from django.urls import path

from .views import CurrentSubscriptionView, PaymentStatusUpdateView, SubscriptionListCreateView

app_name = "subscriptions"

urlpatterns = [
    path("", SubscriptionListCreateView.as_view(), name="list-create"),
    path("status", CurrentSubscriptionView.as_view(), name="status"),
    path("<uuid:pk>/payment-status", PaymentStatusUpdateView.as_view(), name="payment-status"),
]
