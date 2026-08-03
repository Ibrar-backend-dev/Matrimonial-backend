from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.cache import cache
from django.db import IntegrityError
from django.db.models import Q

from apps.matches.models import MatchRequest

from .models import Message

# Fixed-window rate limit: generous enough for normal conversation, tight
# enough to blunt a scripted spam burst. Retune from Phase 11 load-test
# results, not from inspection.
RATE_LIMIT_MAX_MESSAGES = 20
RATE_LIMIT_WINDOW_SECONDS = 10

# Hard cap on how many missed messages a reconnect can pull over the socket --
# a large gap is served through the normal REST history-pagination endpoint
# (apps/chat/views.py) instead of an unbounded WebSocket dump.
MAX_MISSED_MESSAGES = 100


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.match_id = str(self.scope["url_route"]["kwargs"]["match_id"])
        self.group_name = f"match_{self.match_id}"
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not await self.can_access(user.pk):
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        query = parse_qs(self.scope.get("query_string", b"").decode())
        after_id = query.get("after", [None])[0]
        if after_id:
            missed = await self.missed_messages(user.pk, after_id)
            await self.send_json({"type": "missed_messages", "messages": missed})

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        user = self.scope["user"]
        if not await self.check_rate_limit(user.pk):
            await self.send_json({"error": "You're sending messages too quickly. Please slow down."})
            return

        text = str(content.get("message", "")).strip()
        if not text:
            await self.send_json({"error": "A non-empty message is required."})
            return

        client_message_id = content.get("client_message_id")
        if client_message_id is not None:
            client_message_id = str(client_message_id)[:64]

        payload = await self.create_message(user.pk, text, client_message_id)
        if payload is None:
            await self.close(code=4403)
            return
        await self.channel_layer.group_send(self.group_name, {"type": "chat.message", "payload": payload})

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    @sync_to_async
    def check_rate_limit(self, user_id):
        key = f"chat-rate:{user_id}"
        if cache.add(key, 1, timeout=RATE_LIMIT_WINDOW_SECONDS):
            return True
        try:
            count = cache.incr(key)
        except ValueError:
            # Key expired between the add() check and incr() -- fresh window.
            cache.add(key, 1, timeout=RATE_LIMIT_WINDOW_SECONDS)
            return True
        return count <= RATE_LIMIT_MAX_MESSAGES

    @database_sync_to_async
    def can_access(self, user_id):
        return MatchRequest.objects.filter(pk=self.match_id, status="accepted").filter(
            sender_id=user_id
        ).exists() or MatchRequest.objects.filter(
            pk=self.match_id, status="accepted", receiver_id=user_id
        ).exists()

    @database_sync_to_async
    def create_message(self, user_id, text, client_message_id):
        match = MatchRequest.objects.filter(pk=self.match_id, status="accepted").first()
        if not match or user_id not in {match.sender_id, match.receiver_id}:
            return None

        if client_message_id:
            existing = Message.objects.filter(
                match=match, sender_id=user_id, client_message_id=client_message_id
            ).first()
            if existing:
                return self._serialize(existing)
            try:
                message = Message.objects.create(
                    match=match, sender_id=user_id, message=text, client_message_id=client_message_id
                )
            except IntegrityError:
                # Lost a race against an identical retried send committed a
                # moment earlier -- return that row instead of erroring.
                message = Message.objects.get(match=match, sender_id=user_id, client_message_id=client_message_id)
        else:
            message = Message.objects.create(match=match, sender_id=user_id, message=text)
        return self._serialize(message)

    @database_sync_to_async
    def missed_messages(self, user_id, after_id):
        match = MatchRequest.objects.filter(pk=self.match_id, status="accepted").first()
        if not match or user_id not in {match.sender_id, match.receiver_id}:
            return []

        # The cursor id must belong to *this* conversation -- a client can't
        # page through another match's history by guessing/reusing an id.
        cursor_message = Message.objects.filter(pk=after_id, match=match).first()
        if not cursor_message:
            return []

        # Message.id is a random UUID, not a monotonic sequence, so it can't
        # be compared directly for ordering. sent_at is the real ordering
        # signal; id is only a tiebreaker for two messages sharing a
        # timestamp, giving a gap-free, duplicate-free composite cursor.
        messages = (
            Message.objects.filter(match=match)
            .filter(
                Q(sent_at__gt=cursor_message.sent_at)
                | Q(sent_at=cursor_message.sent_at, pk__gt=cursor_message.pk)
            )
            .order_by("sent_at", "pk")[:MAX_MISSED_MESSAGES]
        )
        return [self._serialize(message) for message in messages]

    @staticmethod
    def _serialize(message):
        return {
            "id": str(message.pk),
            "match": str(message.match_id),
            "sender": str(message.sender_id),
            "message": message.message,
            "sent_at": message.sent_at.isoformat(),
            "read_status": message.read_status,
        }
