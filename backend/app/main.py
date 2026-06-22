import os
from fastapi import FastAPI, HTTPException, WebSocket, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from app.services.room_service import RoomService
from app.services.auth_service import hash_password, verify_password, create_token
from app.schemas.auth import (
    User, UserPublic, LoginRequest, LoginResponse,
    CreateUserRequest, CharacterSheet, CharacterSheetPublic,
    CreateCharacterRequest, to_public, sheet_to_public,
)
from app.services.user_storage import UserStorage
from app.deps import user_storage, get_current_user, require_admin, get_current_user_ws
from app.ws.handler import handle_ws_connection

app = FastAPI(title="Dragon Arena")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
room_service = RoomService()


@app.on_event("startup")
def _bootstrap_admin():
    """If users table is empty, seed a default admin account.

    Default credentials: admin / admin123
    CHANGE PASSWORD IMMEDIATELY after first login via admin panel.
    """
    from app.services.auth_service import hash_password
    users = user_storage.list_users()
    if users:
        return
    default_nick = os.environ.get("DRAGON_ARENA_DEFAULT_ADMIN", "admin")
    default_pw = os.environ.get("DRAGON_ARENA_DEFAULT_PASSWORD", "admin123")
    user_storage.create_user(default_nick, hash_password(default_pw), is_admin=True)
    print("=" * 60)
    print(f"  [BOOTSTRAP] Created default admin account")
    print(f"  nickname : {default_nick}")
    print(f"  password : {default_pw}")
    print(f"  !!! Change this via admin panel ASAP")
    print("=" * 60)


# ---- Legacy room CRUD (now requires auth) ----

class CreateRoomReq(BaseModel):
    name: str


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


# ---- Auth ----

@app.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    user = user_storage.get_user_by_nickname(req.nickname)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    user_storage.update_last_login(user.id)
    token = create_token(user.id, user.is_admin)
    return LoginResponse(token=token, user=to_public(user))


@app.get("/auth/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)):
    return to_public(user)


# ---- Admin user management ----

@app.get("/admin/users", response_model=List[UserPublic], dependencies=[Depends(require_admin)])
async def list_users():
    return [to_public(u) for u in user_storage.list_users()]


@app.post("/admin/users", response_model=UserPublic, dependencies=[Depends(require_admin)])
async def create_user(req: CreateUserRequest):
    if user_storage.get_user_by_nickname(req.nickname):
        raise HTTPException(409, "nickname already exists")
    pw_hash = hash_password(req.password)
    user = user_storage.create_user(req.nickname, pw_hash, is_admin=req.is_admin)
    return to_public(user)


@app.delete("/admin/users/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(user_id: str):
    if not user_storage.delete_user(user_id):
        raise HTTPException(404, "user not found")
    return {"ok": True}


# ---- Character sheets ----

@app.get("/characters", response_model=List[CharacterSheet])
async def list_my_characters(user: User = Depends(get_current_user)):
    """Owner sees full field set including secret_backups."""
    return user_storage.list_characters_by_owner(user.id)


@app.post("/characters", response_model=CharacterSheet)
async def create_character(req: CreateCharacterRequest, user: User = Depends(get_current_user)):
    import time, uuid
    sheet = CharacterSheet(
        id=str(uuid.uuid4()), owner_id=user.id,
        name=req.name, gender=req.gender, profession=req.profession, talent=req.talent,
        hp_base=req.hp_base, armor_base=req.armor_base, ap_base=req.ap_base,
        gold=req.gold, backpack=req.backpack,
        equipment_slots=req.equipment_slots, skill_slots=req.skill_slots,
        secret_backups=req.secret_backups,
        created_at=int(time.time() * 1000), updated_at=int(time.time() * 1000),
    )
    return user_storage.create_character(sheet)


@app.put("/characters/{sheet_id}", response_model=CharacterSheet)
async def update_character(sheet_id: str, req: CreateCharacterRequest,
                           user: User = Depends(get_current_user)):
    sheet = user_storage.get_character(sheet_id)
    if not sheet:
        raise HTTPException(404, "character not found")
    if sheet.owner_id != user.id:
        raise HTTPException(403, "not owner")
    sheet.name = req.name
    sheet.gender = req.gender
    sheet.profession = req.profession
    sheet.talent = req.talent
    sheet.hp_base = req.hp_base
    sheet.armor_base = req.armor_base
    sheet.ap_base = req.ap_base
    sheet.gold = req.gold
    sheet.backpack = req.backpack
    sheet.equipment_slots = req.equipment_slots
    sheet.skill_slots = req.skill_slots
    sheet.secret_backups = req.secret_backups
    if not user_storage.update_character(sheet):
        raise HTTPException(500, "update failed")
    return sheet


@app.delete("/characters/{sheet_id}")
async def delete_character(sheet_id: str, user: User = Depends(get_current_user)):
    sheet = user_storage.get_character(sheet_id)
    if not sheet:
        raise HTTPException(404, "character not found")
    if sheet.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "not owner")
    user_storage.delete_character(sheet_id, sheet.owner_id)
    return {"ok": True}


@app.get("/characters/{sheet_id}")
async def get_character(sheet_id: str, user: User = Depends(get_current_user)):
    """Owner/admin see full sheet; others see public version (no secret_backups)."""
    sheet = user_storage.get_character(sheet_id)
    if not sheet:
        raise HTTPException(404, "character not found")
    if sheet.owner_id == user.id or user.is_admin:
        return sheet
    return sheet_to_public(sheet)


# ---- Rooms (now auth-gated) ----

@app.post("/rooms")
async def create_room(req: CreateRoomReq, user: User = Depends(get_current_user)):
    return room_service.create_room(name=req.name, host_id=user.id).model_dump()


@app.get("/rooms")
async def list_rooms(user: User = Depends(get_current_user)):
    return [r.model_dump() for r in room_service.list_rooms()]


@app.get("/rooms/{room_id}")
async def get_room(room_id: str, user: User = Depends(get_current_user)):
    room = room_service.get_room(room_id)
    if not room:
        raise HTTPException(404, "room not found")
    return room.model_dump()


@app.patch("/rooms/{room_id}/config", dependencies=[Depends(get_current_user)])
async def update_config(room_id: str, req: UpdateConfigReq):
    room = room_service.get_room(room_id)
    if not room:
        raise HTTPException(404, "room not found")
    room.config = room.config.model_copy(update=req.model_dump(exclude_none=True))
    return room.model_dump()


@app.websocket("/ws/{room_id}")
async def ws_endpoint(websocket: WebSocket, room_id: str,
                      player_id: str = "", nickname: str = "",
                      token: Optional[str] = None):
    # Auth via query param ?token=...
    user = await get_current_user_ws(websocket)
    if not user:
        await websocket.close(code=4401, reason="unauthorized")
        return
    await handle_ws_connection(
        websocket, room_id, user_id=user.id, nickname=user.nickname,
        room_service=room_service, user=user,
    )
