import uuid
import time
from typing import Optional
from app.schemas.room import Room
from app.schemas.map import GameMap
from app.schemas.chat import ChatMessage
from app.services.geometry_service import chebyshev_distance, has_wall_between


class ChatService:
    def __init__(self, room: Room, game_map: GameMap):
        self.room = room
        self.map = game_map
        self.cfg = room.config

    def _find_token_by_owner(self, player_id: str):
        for t in self.room.tokens.values():
            if t.owner_id == player_id and not t.is_dead:
                return t
        return None

    def send(self, sender_player_id: str, channel: str, text: str = "",
             target_player: Optional[str] = None) -> Optional[ChatMessage]:
        if channel in ("spatial_normal", "spatial_shout"):
            return self._send_spatial(sender_player_id, channel, text)
        if channel == "hall":
            return self._send_broadcast(sender_player_id, "hall", text)
        if channel == "battle":
            return self._send_broadcast(sender_player_id, "battle", text)
        if channel == "private" and target_player:
            return self._send_private(sender_player_id, target_player, text)
        return None

    def _send_broadcast(self, sender: str, channel: str, text: str) -> ChatMessage:
        return ChatMessage(
            id=str(uuid.uuid4()), sender_id=sender, channel=channel,
            content_type="text", text=text, recipients=None,
            timestamp=int(time.time() * 1000),
        )

    def _send_private(self, sender: str, target: str, text: str) -> ChatMessage:
        return ChatMessage(
            id=str(uuid.uuid4()), sender_id=sender, channel="private",
            content_type="text", text=text, recipients=[sender, target],
            timestamp=int(time.time() * 1000),
        )

    def _send_spatial(self, sender_player_id: str, channel: str, text: str) -> Optional[ChatMessage]:
        sender_token = self._find_token_by_owner(sender_player_id)
        if not sender_token or not sender_token.position or sender_token.is_dead:
            return None
        is_shout = channel == "spatial_shout"
        radius = (self.cfg.speak_radius * self.cfg.shout_multiplier) if is_shout else self.cfg.speak_radius
        origin = (sender_token.position["x"], sender_token.position["y"])
        recipients = []
        for other in self.room.tokens.values():
            if other.owner_id == sender_player_id or other.is_dead or not other.position:
                continue
            target_pos = (other.position["x"], other.position["y"])
            dist = chebyshev_distance(origin, target_pos)
            if dist > radius:
                continue
            if not self.cfg.sound_through_wall and has_wall_between(self.map, origin, target_pos):
                continue
            recipients.append(other.owner_id)
        # 衰减：距离越远，声音越小（模拟）
        attenuation = min(1.0, radius / max(1, self.cfg.speak_radius))
        return ChatMessage(
            id=str(uuid.uuid4()), sender_id=sender_player_id, channel=channel,
            content_type="text", text=text, recipients=recipients,
            timestamp=int(time.time() * 1000),
            extra={"attenuation": attenuation, "distance": dist, "is_shout": is_shout},
        )
