from typing import Dict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, room_id: str, player_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.rooms.setdefault(room_id, {})[player_id] = ws

    def disconnect(self, room_id: str, player_id: str) -> None:
        if room_id in self.rooms:
            self.rooms[room_id].pop(player_id, None)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

    async def send_to_player(self, room_id: str, player_id: str, data: dict) -> None:
        ws = self.rooms.get(room_id, {}).get(player_id)
        if ws:
            await ws.send_json(data)

    async def send_to_players(self, room_id: str, player_ids: list, data: dict) -> None:
        for pid in player_ids:
            await self.send_to_player(room_id, pid, data)

    async def broadcast(self, room_id: str, data: dict) -> None:
        for ws in self.rooms.get(room_id, {}).values():
            await ws.send_json(data)
