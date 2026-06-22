import time
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect
from app.services.room_service import RoomService
from app.services.chat_service import ChatService
from app.services.dice_service import roll_dice
from app.services.token_service import TokenService
from app.services.turn_service import TurnService
from app.services.vision_service import VisionService
from app.services.event_log_service import EventLogService
from app.services.map_service import MapService
from app.schemas.map import GameMap
from app.schemas.event import GameEvent
from app.schemas.room import Player
from .connection_manager import ConnectionManager


class RoomGameState:
    def __init__(self, room):
        self.room = room
        self.game_map = GameMap(width=room.config.map_width, height=room.config.map_height)
        self.map_svc = MapService(self.game_map)
        self.token_svc = TokenService(room, self.game_map)
        self.vision_svc = VisionService(room, self.game_map)
        self.chat_svc = ChatService(room, self.game_map)
        self.turn_svc = TurnService(room)
        self.event_log = EventLogService()


room_game_states: Dict[str, RoomGameState] = {}
connection_mgr = ConnectionManager()


def get_game_state(room_id: str, room_service: RoomService) -> RoomGameState:
    if room_id not in room_game_states:
        room = room_service.get_room(room_id)
        if not room:
            return None
        room_game_states[room_id] = RoomGameState(room)
    return room_game_states[room_id]


def _log_event(gs: RoomGameState, actor: str, action: str, **kwargs):
    gs.event_log.log(GameEvent(
        timestamp=int(time.time() * 1000),
        big_turn=gs.room.big_turn, sub_turn=gs.room.sub_turn,
        actor=actor, action=action, **kwargs,
    ))


async def handle_ws_connection(websocket: WebSocket, room_id: str, user_id: str,
                                nickname: str, room_service: RoomService, user=None):
    room = room_service.get_room(room_id)
    if not room:
        await websocket.close(code=4004, reason="room not found")
        return
    # Player.id == User.id for simplicity
    player_id = user_id
    await connection_mgr.connect(room_id, player_id, websocket)
    if player_id not in room.players:
        room.players[player_id] = Player(
            id=player_id, name=nickname or player_id, nickname=nickname,
            is_host=False, is_connected=True,
        )
    room.players[player_id].is_connected = True

    await connection_mgr.send_to_player(room_id, player_id, {
        "type": "state_sync", "payload": room.model_dump(),
    })

    gs = get_game_state(room_id, room_service)
    if not gs:
        return

    try:
        while True:
            data = await websocket.receive_json()
            t = data.get("type")
            p = data.get("payload", {})
            if t == "chat":
                msg = gs.chat_svc.send(player_id, p.get("channel", "hall"),
                                       text=p.get("text", ""),
                                       target_player=p.get("target_player"))
                if msg:
                    _log_event(gs, player_id, "send_message",
                               params={"channel": msg.channel}, target=p.get("target_player"))
                    out = {"type": "chat", "payload": msg.model_dump()}
                    if msg.recipients is None:
                        await connection_mgr.broadcast(room_id, out)
                    else:
                        await connection_mgr.send_to_players(room_id, msg.recipients, out)
            elif t == "dice_roll":
                r = roll_dice(sides=p.get("sides", 20), modifier=p.get("modifier", 0),
                              crit_success_threshold=gs.room.config.crit_success,
                              crit_fail_threshold=gs.room.config.crit_fail)
                _log_event(gs, player_id, "dice", params=p, result=r.model_dump())
                await connection_mgr.broadcast(room_id, {
                    "type": "dice_result", "payload": {"actor": player_id, **r.model_dump()},
                })
            elif t == "move":
                result = gs.token_svc.move_along_path(
                    p.get("token_id"), [tuple(x) for x in p.get("path", [])])
                _log_event(gs, player_id, "move", target=p.get("token_id"),
                           params={"path": p.get("path", [])}, result=result.model_dump())
                await _broadcast_state(gs, room_id)
            elif t == "modify_value":
                gs.token_svc.modify_value(p.get("token_id"), p.get("field"), p.get("delta", 0))
                _log_event(gs, player_id, "modify_value", target=p.get("token_id"), params=p)
                await _broadcast_state(gs, room_id)
            elif t == "add_state":
                gs.token_svc.add_state(p.get("token_id"),
                                       state_id=p.get("state_id", f"s{int(time.time()*1000)}"),
                                       name=p.get("name", ""), description=p.get("description", ""),
                                       ttl=p.get("ttl", 1), intensity=p.get("intensity"))
                _log_event(gs, player_id, "add_state", target=p.get("token_id"), params=p)
                await _broadcast_state(gs, room_id)
            elif t == "place_token":
                gs.token_svc.place_token(p.get("token_id"), p.get("x"), p.get("y"))
                _log_event(gs, player_id, "place_token", target=p.get("token_id"), params=p)
                await _broadcast_state(gs, room_id)
            elif t == "set_terrain":
                gs.map_svc.set_terrain(p.get("x"), p.get("y"), p.get("type", "flat"))
                _log_event(gs, player_id, "set_terrain", params=p)
                await _broadcast_state(gs, room_id)
            elif t == "end_turn":
                gs.turn_svc.end_turn()
                _log_event(gs, player_id, "end_turn")
                await _broadcast_state(gs, room_id)
            elif t == "set_turn_order":
                gs.turn_svc.set_order(p.get("order", []))
                _log_event(gs, player_id, "set_turn_order", params=p)
                await _broadcast_state(gs, room_id)
            elif t == "start_game":
                gs.turn_svc.start()
                _log_event(gs, player_id, "start_game")
                await _broadcast_state(gs, room_id)
            else:
                await connection_mgr.send_to_player(room_id, player_id, {
                    "type": "error", "payload": {"message": f"unknown type: {t}"}
                })
    except WebSocketDisconnect:
        connection_mgr.disconnect(room_id, player_id)
        if player_id in room.players:
            room.players[player_id].is_connected = False


async def _broadcast_state(gs: RoomGameState, room_id: str):
    await connection_mgr.broadcast(room_id, {
        "type": "state_sync", "payload": gs.room.model_dump(),
    })
