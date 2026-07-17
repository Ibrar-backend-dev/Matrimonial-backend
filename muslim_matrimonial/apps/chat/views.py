from rest_framework import generics

from .models import Message
from .permissions import CanAccessAcceptedMatch
from .serializers import MessageSerializer


class MessageHistoryView(generics.ListAPIView):
    serializer_class = MessageSerializer
    permission_classes = [CanAccessAcceptedMatch]

    def get_queryset(self):
        return Message.objects.filter(match_id=self.kwargs["match_id"]).select_related("sender")
