from django.test import TestCase

from apps.matches.models import MatchRequest
from apps.users.models import User

from .models import Message


class MessageRulesTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(phone="+921111111111")
        self.receiver = User.objects.create_user(phone="+922222222222")

    def test_pending_match_cannot_receive_messages(self):
        match = MatchRequest.objects.create(sender=self.sender, receiver=self.receiver)
        with self.assertRaisesMessage(ValueError, "not accepted"):
            Message.objects.create(match=match, sender=self.sender, message="Assalamu alaikum")

    def test_accepted_match_can_receive_messages(self):
        match = MatchRequest.objects.create(sender=self.sender, receiver=self.receiver, status="accepted")
        message = Message.objects.create(match=match, sender=self.sender, message="Assalamu alaikum")
        self.assertEqual(message.match, match)
