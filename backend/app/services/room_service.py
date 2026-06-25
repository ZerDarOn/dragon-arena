import uuid
from typing import Dict, List, Optional
from app.schemas.room import Room, Player


class RoomService:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def create_room(self, name: str, host_id: str, host_nickname: str = "") -> Room:
        room_id = str(uuid.uuid4())[:8]
        room = Room(id=room_id, name=name)
        room.players[host_id] = Player(
            id=host_id, name=host_nickname or host_id, nickname=host_nickname,
            is_host=True, is_connected=True,
        )
        self.rooms[room_id] = room
        return room

    def join_room(self, room_id: str, player_id: str, nickname: str = "") -> Optional[Room]:
        room = self.rooms.get(room_id)
        if not room:
            return None
        room.players[player_id] = Player(
            id=player_id, name=player_id, nickname=nickname,
            is_host=False, is_connected=True,
        )
        return room

    def leave_room(self, room_id: str, player_id: str) -> None:
        room = self.rooms.get(room_id)
        if room and player_id in room.players:
            room.players[player_id].is_connected = False

    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def list_rooms(self) -> List[Room]:
        return list(self.rooms.values())

    def delete_room(self, room_id: str) -> None:
        self.rooms.pop(room_id, None)
