from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.matches.models import MatchRequest

from .models import Message


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

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        text = str(content.get("message", "")).strip()
        if not text:
            await self.send_json({"error": "A non-empty message is required."})
            return
        payload = await self.create_message(self.scope["user"].pk, text)
        if payload is None:
            await self.close(code=4403)
            return
        await self.channel_layer.group_send(self.group_name, {"type": "chat.message", "payload": payload})

    async def chat_message(self, event):
        await self.send_json(event["payload"])

    @database_sync_to_async
    def can_access(self, user_id):
        return MatchRequest.objects.filter(pk=self.match_id, status="accepted").filter(
            sender_id=user_id
        ).exists() or MatchRequest.objects.filter(
            pk=self.match_id, status="accepted", receiver_id=user_id
        ).exists()

    @database_sync_to_async
    def create_message(self, user_id, text):
        match = MatchRequest.objects.filter(pk=self.match_id, status="accepted").first()
        if not match or user_id not in {match.sender_id, match.receiver_id}:
            return None
        message = Message.objects.create(match=match, sender_id=user_id, message=text)
        return {
            "id": str(message.pk),
            "match": str(match.pk),
            "sender": str(user_id),
            "message": message.message,
            "sent_at": message.sent_at.isoformat(),
            "read_status": message.read_status,
        }
