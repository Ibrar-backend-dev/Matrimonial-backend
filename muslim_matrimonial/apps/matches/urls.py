from django.urls import path

from .views import MatchFilterView, MatchRequestCreateView, MatchRespondView, SuggestionListView

app_name = "matches"

urlpatterns = [
    path("suggestions", SuggestionListView.as_view(), name="suggestions"),
    path("filter", MatchFilterView.as_view(), name="filter"),
    path("request/<uuid:user_id>", MatchRequestCreateView.as_view(), name="request"),
    path("respond/<uuid:request_id>", MatchRespondView.as_view(), name="respond"),
]
