import os
from fastapi import FastAPI, HTTPException, WebSocket, Depends, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
from app.schemas.actor import ActorCreate, ActorUpdate
from app.schemas.item import ItemCreate, ItemUpdate
from app.schemas.library import LibraryEntry
from app.services.library_service import library_service
from app.schemas.rolltable import RollTable, RollEntry, DrawResult
from app.services.rolltable_service import rolltable_service

app = FastAPI(title="Dragon Arena")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)
room_service = RoomService()

# 确保上传目录存在
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

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


@app.get("/admin/characters", response_model=List[CharacterSheet])
async def list_all_characters(user: User = Depends(require_admin)):
    """Admin only: all character sheets with secret_backups."""
    return user_storage.list_all_characters()


@app.post("/characters", response_model=CharacterSheet)
async def create_character(req: CreateCharacterRequest, user: User = Depends(get_current_user)):
    import time, uuid
    sheet = CharacterSheet(
        id=str(uuid.uuid4()), owner_id=user.id,
        name=req.name, avatar_url=req.avatar_url, gender=req.gender, profession=req.profession, talent=req.talent,
        hp_base=req.hp_base, armor_base=req.armor_base, ap_base=req.ap_base,
        gold=req.gold, backpack=req.backpack,
        equipment_slots=req.equipment_slots, skill_slots=req.skill_slots,
        secret_backups=req.secret_backups,
        darkvision=req.darkvision, vision_range=req.vision_range,
        listen_radius=req.listen_radius,
        passive_perception=req.passive_perception, stealth=req.stealth,
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
    sheet.avatar_url = req.avatar_url
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
    sheet.darkvision = req.darkvision
    sheet.vision_range = req.vision_range
    sheet.listen_radius = req.listen_radius
    sheet.passive_perception = req.passive_perception
    sheet.stealth = req.stealth
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
    return room_service.create_room(name=req.name, host_id=user.id, host_nickname=user.nickname).model_dump()


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


# ---- Actor Library (角色卡模板库) ----

@app.get("/api/actors", dependencies=[Depends(get_current_user)])
async def list_actors(type: Optional[str] = None):
    return user_storage.list_actors(type=type)


@app.post("/api/actors", dependencies=[Depends(require_admin)])
async def create_actor(req: ActorCreate):
    return user_storage.create_actor(req)


@app.put("/api/actors/{actor_id}", dependencies=[Depends(require_admin)])
async def update_actor(actor_id: str, req: ActorUpdate):
    actor = user_storage.update_actor(actor_id, req)
    if not actor:
        raise HTTPException(404, "actor not found")
    return actor


@app.delete("/api/actors/{actor_id}", dependencies=[Depends(require_admin)])
async def delete_actor(actor_id: str):
    if not user_storage.delete_actor(actor_id):
        raise HTTPException(404, "actor not found")
    return {"ok": True}


# ---- Item Library (道具库) ----

@app.get("/api/items", dependencies=[Depends(get_current_user)])
async def list_items(category: Optional[str] = None):
    return user_storage.list_items(category=category)


@app.post("/api/items", dependencies=[Depends(require_admin)])
async def create_item(req: ItemCreate):
    return user_storage.create_item(req)


@app.put("/api/items/{item_id}", dependencies=[Depends(require_admin)])
async def update_item(item_id: str, req: ItemUpdate):
    item = user_storage.update_item(item_id, req)
    if not item:
        raise HTTPException(404, "item not found")
    return item


@app.delete("/api/items/{item_id}", dependencies=[Depends(require_admin)])
async def delete_item(item_id: str):
    if not user_storage.delete_item(item_id):
        raise HTTPException(404, "item not found")
    return {"ok": True}


class ItemImportRequest(BaseModel):
    entries: List[dict]
    mode: Optional[str] = "upsert"   # upsert(按name合并) | replace


@app.post("/api/items/import", dependencies=[Depends(require_admin)])
async def import_items(req: ItemImportRequest):
    """批量导入道具（管理员）。entries 与导出/ItemCreate 同字段，按 name upsert。"""
    try:
        return user_storage.import_items(req.entries, mode=req.mode or "upsert")
    except Exception as e:
        raise HTTPException(400, f"导入失败：{e}")


# ---- 内容库（事件/陷阱/怪物/奇遇/NPC）只读参考 ----

@app.get("/api/library", response_model=List[LibraryEntry], dependencies=[Depends(get_current_user)])
async def list_library(category: Optional[str] = None):
    """所有登录用户可读。category 可选：event|trap|monster|adventure|npc。
    无 category 时返回全部——也作为「导出」用：前端直接把这个数组存成文件即可。"""
    return library_service.list(category)


class LibraryImportRequest(BaseModel):
    entries: List[dict]
    mode: Optional[str] = "upsert"   # upsert | replace


@app.post("/api/library/import", dependencies=[Depends(require_admin)])
async def import_library(req: LibraryImportRequest):
    """导入内容库（仅管理员）。entries 为 LibraryEntry 数组（与导出格式一致，id 可省略）。
    格式即规范：AI 读 Excel 整理成这个数组就能一键导入。"""
    try:
        return library_service.import_entries(req.entries, mode=req.mode or "upsert")
    except Exception as e:
        raise HTTPException(400, f"导入失败：{e}")


# ---- 抽取表（RollTable）----

class RollTableInput(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    source_category: str = ""
    entries: List[RollEntry] = []


@app.get("/api/rolltables", response_model=List[RollTable], dependencies=[Depends(get_current_user)])
async def list_rolltables():
    return rolltable_service.list()


@app.post("/api/rolltables", response_model=RollTable, dependencies=[Depends(require_admin)])
async def create_rolltable(req: RollTableInput):
    return rolltable_service.create(req.model_dump(exclude_none=True))


@app.put("/api/rolltables/{tid}", response_model=RollTable, dependencies=[Depends(require_admin)])
async def update_rolltable(tid: str, req: RollTableInput):
    t = rolltable_service.update(tid, req.model_dump(exclude_none=True))
    if not t:
        raise HTTPException(404, "rolltable not found")
    return t


@app.delete("/api/rolltables/{tid}", dependencies=[Depends(require_admin)])
async def delete_rolltable(tid: str):
    if not rolltable_service.delete(tid):
        raise HTTPException(404, "rolltable not found")
    return {"ok": True}


@app.post("/api/rolltables/{tid}/draw", response_model=DrawResult, dependencies=[Depends(get_current_user)])
async def draw_rolltable(tid: str):
    """抽一次（服务端权威）。所有登录用户可抽——团主用得最多。"""
    r = rolltable_service.draw(tid)
    if not r:
        raise HTTPException(404, "rolltable not found")
    return r


# ---- 头像上传 ----

@app.post("/api/upload/avatar", dependencies=[Depends(get_current_user)])
async def upload_avatar(file: UploadFile = File(...)):
    """上传头像图片，返回可访问 URL。支持 png/jpg/gif/webp，最大 2MB。"""
    ALLOWED_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
    MAX_SIZE = 2 * 1024 * 1024  # 2MB

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "只支持 png/jpg/gif/webp 图片")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "图片超过 2MB 限制")

    ext = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}.get(file.content_type, "bin")
    import uuid, time
    filename = f"avatar_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    # 返回相对 URL（前端通过 /uploads/... 访问）
    return {"url": f"/uploads/{filename}"}


@app.post("/api/upload/map", dependencies=[Depends(get_current_user)])
async def upload_map_bg(file: UploadFile = File(...)):
    """上传场景底图，返回可访问 URL。支持 png/jpg/webp，最大 10MB。"""
    ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp"}
    MAX_SIZE = 10 * 1024 * 1024  # 10MB

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "只支持 png/jpg/webp 图片")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, "底图超过 10MB 限制")

    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(file.content_type, "bin")
    import uuid, time
    filename = f"map_{int(time.time())}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/{filename}"}


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
