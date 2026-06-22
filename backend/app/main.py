from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from app.services.room_service import RoomService
from app.ws.handler import handle_ws_connection

app = FastAPI(title="Dragon Arena")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
room_service = RoomService()


class CreateRoomReq(BaseModel):
    name: str
    host_id: str


class UpdateConfigReq(BaseModel):
    map_width: Optional[int] = None
    map_height: Optional[int] = None
    vision_range: Optional[int] = None
    move_ap_cost: Optional[int] = None
    sprint_ap_cost: Optional[int] = None
    sprint_distance: Optional[int] = None
    start_hp: Optional[int] = None
    start_armor: Optional[int] = None
    start_ap: Optional[int] = None
    creation_points: Optional[int] = None
    dc_melee: Optional[int] = None
    dc_mid: Optional[int] = None
    dc_ranged: Optional[int] = None
    crit_success: Optional[int] = None
    crit_fail: Optional[int] = None
    defend_ap_cost: Optional[int] = None
    speak_radius: Optional[int] = None
    shout_multiplier: Optional[int] = None
    sound_through_wall: Optional[bool] = None
    turn_time_limit_sec: Optional[int] = None
    ap_regen: Optional[int] = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/rooms")
async def create_room(req: CreateRoomReq):
    return room_service.create_room(name=req.name, host_id=req.host_id).model_dump()


@app.get("/rooms")
async def list_rooms():
    return [r.model_dump() for r in room_service.list_rooms()]


@app.get("/rooms/{room_id}")
async def get_room(room_id: str):
    room = room_service.get_room(room_id)
    if not room:
        raise HTTPException(404, "room not found")
    return room.model_dump()


@app.patch("/rooms/{room_id}/config")
async def update_config(room_id: str, req: UpdateConfigReq):
    room = room_service.get_room(room_id)
    if not room:
        raise HTTPException(404, "room not found")
    room.config = room.config.model_copy(update=req.model_dump(exclude_none=True))
    return room.model_dump()


@app.websocket("/ws/{room_id}")
async def ws_endpoint(websocket: WebSocket, room_id: str,
                      player_id: str = "", nickname: str = ""):
    await handle_ws_connection(websocket, room_id, player_id, nickname, room_service)
