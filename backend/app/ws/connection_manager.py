from typing import Dict, Set
from fastapi import WebSocket
import asyncio

class ConnectionManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[str, WebSocket]] = {}
        self.admins: Dict[str, Set[str]] = {}  # room_id -> {player_id, ...}
        self._locks: Dict[str, asyncio.Lock] = {}  # per-room broadcast lock

    async def connect(self, room_id: str, player_id: str, ws: WebSocket,
                      is_admin: bool = False) -> None:
        await ws.accept()
        self.rooms.setdefault(room_id, {})[player_id] = ws
        if is_admin:
            self.admins.setdefault(room_id, set()).add(player_id)

    def disconnect(self, room_id: str, player_id: str) -> None:
        if room_id in self.rooms:
            self.rooms[room_id].pop(player_id, None)
            if not self.rooms[room_id]:
                del self.rooms[room_id]
        if room_id in self.admins:
            self.admins[room_id].discard(player_id)
            if not self.admins[room_id]:
                del self.admins[room_id]

    def is_admin(self, room_id: str, player_id: str) -> bool:
        return player_id in self.admins.get(room_id, set())

    def players_in_room(self, room_id: str):
        return list(self.rooms.get(room_id, {}).keys())

    async def send_to_player(self, room_id: str, player_id: str, data: dict) -> None:
        ws = self.rooms.get(room_id, {}).get(player_id)
        if ws:
            await ws.send_json(data)

    async def send_to_players(self, room_id: str, player_ids: list, data: dict) -> None:
        for pid in player_ids:
            await self.send_to_player(room_id, pid, data)

    async def broadcast(self, room_id: str, data: dict) -> None:
        """串行化广播，避免 websockets 并发 send_json 导致 AssertionError。"""
        lock = self._locks.setdefault(room_id, asyncio.Lock())
        async with lock:
            for ws in list(self.rooms.get(room_id, {}).values()):
                try:
                    await ws.send_json(data)
                except Exception:
                    pass  # 连接断开时忽略
