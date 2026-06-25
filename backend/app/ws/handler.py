import asyncio
import time
from typing import Dict
from fastapi import WebSocket, WebSocketDisconnect
from app.services.room_service import RoomService
from app.services.chat_service import ChatService
from app.services.dice_service import roll_dice, roll_expression
from app.services.token_service import TokenService
from app.services.turn_service import TurnService
from app.services.vision_service import VisionService
from app.services.event_log_service import EventLogService
from app.services.map_service import MapService
from app.services.room_snapshot_storage import RoomSnapshotStorage
from app.services.combat_engine import CombatEngine, CombatContext, create_attack_rule
from app.schemas.map import GameMap
from app.schemas.event import GameEvent
from app.schemas.room import Player, Token
from app.deps import user_storage
from .connection_manager import ConnectionManager

connection_mgr = ConnectionManager()


class RoomGameState:
    def __init__(self, room):
        self.room = room
        self.game_map = GameMap(width=room.config.map_width, height=room.config.map_height)
        # Bind map to room so state_sync includes terrain
        self.room.game_map = self.game_map
        self.map_svc = MapService(self.game_map)
        self.token_svc = TokenService(room, self.game_map)
        self.vision_svc = VisionService(room, self.game_map)
        self.chat_svc = ChatService(room, self.game_map)
        self.turn_svc = TurnService(room)
        self.event_log = EventLogService()
        self.combat_engine = CombatEngine()
        # 并发安全 + 持久化（Phase 1）
        self.lock = asyncio.Lock()
        self.snapshot_storage = None  # 外部注入（handler 启动时）
        # Phase 2: 回合时限
        self.turn_timer: asyncio.Task | None = None
        self.turn_deadline: float | None = None  # Unix 时间戳，前端用 (deadline - now) 渲染倒计时

    def _get_distance(self, a: Token, b: Token) -> int:
        if not a.position or not b.position:
            return 0
        return max(abs(a.position["x"] - b.position["x"]), abs(a.position["y"] - b.position["y"]))

    def _register_default_attack_rules(self, token: Token):
        """为 token 注册默认攻击规则（基于装备）。"""
        # 检查装备槽判断武器类型
        has_ranged = any("狙击" in (s or "") or "步枪" in (s or "") or "弓" in (s or "") for s in token.equipment_slots)
        has_melee = any("剑" in (s or "") or "刀" in (s or "") or "拳" in (s or "") or "爪" in (s or "") for s in token.equipment_slots)
        
        if has_ranged:
            self.combat_engine.register_rules(token.id, [
                create_attack_rule("远程攻击", "ranged", base_damage=25, ap_cost=1),
            ])
        elif has_melee:
            self.combat_engine.register_rules(token.id, [
                create_attack_rule("近战攻击", "melee", base_damage=10, dice_expr="D20-8", ap_cost=1),
            ])
        else:
            # 默认徒手
            self.combat_engine.register_rules(token.id, [
                create_attack_rule("徒手攻击", "melee", base_damage=5, dice_expr="D20-8", ap_cost=1),
            ])

    def start_turn_timer(self, callback=None) -> None:
        """启动回合倒计时。超时后自动 end_turn（走锁），然后调 callback（广播）。

        callback 是 async 函数，接收无参数；用于锁外广播。
        时限 <= 0 时不启动（关闭时限）。
        """
        self.cancel_turn_timer()
        limit = self.room.config.turn_time_limit_sec
        if limit <= 0:
            self.turn_deadline = None
            return
        import time as _time
        self.turn_deadline = _time.time() + limit
        self._timer_callback = callback
        self.turn_timer = asyncio.create_task(self._timer_tick(limit))

    def cancel_turn_timer(self) -> None:
        """取消回合倒计时。"""
        if self.turn_timer and not self.turn_timer.done():
            self.turn_timer.cancel()
        self.turn_timer = None
        self.turn_deadline = None

    async def _timer_tick(self, delay: float) -> None:
        """倒计时任务：等待 delay 秒后获取锁 → end_turn → 快照 → callback。"""
        try:
            await asyncio.sleep(delay)
            async with self.lock:
                self.turn_svc.end_turn()
                if self.snapshot_storage:
                    self.snapshot_storage.save(self.room.id, self.room.model_dump_json())
            self.turn_timer = None
            self.turn_deadline = None
            # 广播在锁外
            cb = getattr(self, "_timer_callback", None)
            if cb:
                import inspect
                result = cb()
                if inspect.isawaitable(result):
                    await result
        except asyncio.CancelledError:
            pass


_game_states: Dict[str, RoomGameState] = {}
_snapshot_storage = None

def _get_snapshot_storage() -> RoomSnapshotStorage:
    global _snapshot_storage
    if _snapshot_storage is None:
        import os
        db_path = os.environ.get("DRAGON_ARENA_DB_PATH", "backend/data/users.db")
        _snapshot_storage = RoomSnapshotStorage(db_path=db_path)
    return _snapshot_storage

def get_game_state(room_id: str, room_service: RoomService) -> RoomGameState | None:
    room = room_service.get_room(room_id)
    if not room:
        return None
    if room_id not in _game_states:
        # Phase 1: 进程重启后从快照恢复
        storage = _get_snapshot_storage()
        snapshot_json = storage.load(room_id)
        if snapshot_json is not None:
            try:
                room = Room.model_validate_json(snapshot_json)
            except Exception:
                # 快照损坏则回退到 room_service 的原始 room
                pass
        gs = RoomGameState(room)
        gs.snapshot_storage = storage
        _game_states[room_id] = gs
    return _game_states[room_id]

def _log_event(gs: RoomGameState, player_id: str, action: str, target: str = None,
               params: dict = None, result=None):
    """记录游戏事件到事件日志。"""
    gs.event_log.log(GameEvent(
        timestamp=int(time.time()),
        big_turn=gs.room.big_turn,
        sub_turn=gs.room.sub_turn,
        actor=player_id,
        action=action,
        target=target,
        params=params or {},
        result=result,
    ))


async def handle_ws_connection(websocket: WebSocket, room_id: str, user_id: str,
                                nickname: str, room_service: RoomService, user=None):
    room = room_service.get_room(room_id)
    if not room:
        await websocket.close(code=4004, reason="room not found")
        return
    # Player.id == User.id for simplicity
    player_id = user_id
    is_admin = bool(user and getattr(user, "is_admin", False))
    await connection_mgr.connect(room_id, player_id, websocket, is_admin=is_admin)
    if player_id not in room.players:
        room.players[player_id] = Player(
            id=player_id, name=nickname or player_id, nickname=nickname,
            is_host=False, is_connected=True,
        )
    elif nickname and not room.players[player_id].nickname:
        # 房主的 Player 记录是在 /rooms 建房时就创建的（早于 WS 连接），
        # 当时没有 nickname；这里补上，否则房主永远显示成一串 user id。
        room.players[player_id].nickname = nickname
    room.players[player_id].is_connected = True

    gs = get_game_state(room_id, room_service)
    if not gs:
        return
    # 初次推送：按玩家定制
    await _send_state_to_player(gs, room_id, player_id)

    try:
        while True:
            data = await websocket.receive_json()
            try:
                t = data.get("type")
                p = data.get("payload", {})
                if t == "chat":
                    msg = gs.chat_svc.send(player_id, p.get("channel", "hall"),
                                           text=p.get("text", ""),
                                           target_player=p.get("target_player"),
                                           is_admin=is_admin)
                    if msg:
                        _log_event(gs, player_id, "send_message",
                                   params={"channel": msg.channel}, target=p.get("target_player"))
                        out = {"type": "chat", "payload": msg.model_dump()}
                        if msg.recipients is None:
                            await connection_mgr.broadcast(room_id, out)
                        else:
                            await connection_mgr.send_to_players(room_id, msg.recipients, out)
                    else:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "消息发送失败：频道不可用或没有权限"}
                        })
                elif t == "dice_roll":
                    # 新版传 expression（如 "2d20kh1+5"）；旧版传 sides/modifier，
                    # 在这里拼成一个等价表达式，统一走一套引擎，不留两份逻辑。
                    expr = p.get("expression")
                    if not expr:
                        sides_legacy = p.get("sides", 20)
                        mod_legacy = p.get("modifier", 0)
                        expr = f"1d{sides_legacy}{mod_legacy:+d}" if mod_legacy else f"1d{sides_legacy}"
                    r = roll_expression(expr,
                                        crit_success_threshold=gs.room.config.crit_success,
                                        crit_fail_threshold=gs.room.config.crit_fail,
                                        forced_values=p.get("rolls"))
                    _log_event(gs, player_id, "dice", params=p, result=r.model_dump())
                    await connection_mgr.broadcast(room_id, {
                        "type": "dice_result", "payload": {"actor": player_id, **r.model_dump()},
                    })
                elif t == "move":
                    tid_m = p.get("token_id")
                    tok_m = gs.room.tokens.get(tid_m)
                    if tok_m and _can_control(tok_m, user, player_id):
                        result = gs.token_svc.move_along_path(
                            tid_m, [tuple(x) for x in p.get("path", [])])
                        _log_event(gs, player_id, "move", target=tid_m,
                                   params={"path": p.get("path", [])}, result=result.model_dump())
                    await _broadcast_state(gs, room_id)
                elif t == "modify_value":
                    tid_v = p.get("token_id")
                    tok_v = gs.room.tokens.get(tid_v)
                    # 数值修改：仅管理员或 owner
                    if tok_v and _can_control(tok_v, user, player_id):
                        gs.token_svc.modify_value(tid_v, p.get("field"), p.get("delta", 0))
                        _log_event(gs, player_id, "modify_value", target=tid_v, params=p)
                    await _broadcast_state(gs, room_id)
                elif t == "add_state":
                    tid_s = p.get("token_id")
                    tok_s = gs.room.tokens.get(tid_s)
                    if tok_s and _can_control(tok_s, user, player_id):
                        gs.token_svc.add_state(tid_s,
                                               state_id=p.get("state_id", f"s{int(time.time()*1000)}"),
                                               name=p.get("name", ""), description=p.get("description", ""),
                                               ttl=p.get("ttl", 1), intensity=p.get("intensity"))
                    _log_event(gs, player_id, "add_state", target=p.get("token_id"), params=p)
                    await _broadcast_state(gs, room_id)
                elif t == "place_token":
                    token_id_pt = p.get("token_id")
                    existing = gs.room.tokens.get(token_id_pt) if token_id_pt else None
                    # 已存在的 token：只有 owner 本人或管理员能再次落子/挪动它
                    # （不存在则视为玩家在认领一个新 token_id，允许）
                    if existing and not _can_control(existing, user, player_id):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "该角色已被其他玩家占用"}
                        })
                        continue
                    character = p.get("character")
                    is_new_claim = existing is None
                    gs.token_svc.place_token(token_id_pt, p.get("x"), p.get("y"), character=character)
                    # 这个 token 真正归属谁：管理员可以代别人摆放（从角色卡列表拖某个
                    # 玩家的卡到地图），此时信任 character.owner_id；非管理员只能摆自己
                    # 的（角色卡列表本来就只会显示自己的卡，但这里仍强制覆盖，防止
                    # 客户端被改过后伪造 owner_id 顶替别人）。
                    claimed_owner = character.get("owner_id") if character else None
                    owner_pid = claimed_owner if (is_admin and claimed_owner) else player_id
                    if token_id_pt:
                        if is_new_claim:
                            gs.room.tokens[token_id_pt].owner_id = owner_pid
                        if owner_pid in gs.room.players:
                            gs.room.players[owner_pid].token_id = token_id_pt
                            if character:
                                gs.room.players[owner_pid].character_name = character.get("name", "")
                                gs.room.players[owner_pid].profession = character.get("profession", "")
                                gs.room.players[owner_pid].gender = character.get("gender", "")
                                gs.room.players[owner_pid].talent = character.get("talent", "")
                    _log_event(gs, player_id, "place_token", target=token_id_pt, params=p)
                    await _broadcast_state(gs, room_id)
                elif t == "place_unit":
                    # DM 放置非玩家单位（怪物/NPC/陷阱/掉落物）
                    if not (user and user.is_admin):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "admin only"}
                        })
                        continue
                    unit_type = p.get("unit_type", "monster")
                    name = p.get("name", unit_type)
                    x, y = int(p.get("x", 0)), int(p.get("y", 0))
                    # 生成唯一 id
                    token_id = f"{unit_type}_{int(time.time() * 1000) % 1000000}"
                    # 占位检查
                    occupied = any(
                        (tok.position == {"x": x, "y": y} and not tok.is_dead)
                        for tok in gs.room.tokens.values()
                    )
                    if occupied:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "cell occupied"}
                        })
                        continue
                    hp = int(p.get("hp", 50))
                    gs.room.tokens[token_id] = Token(
                        id=token_id, type=unit_type, position={"x": x, "y": y},
                        character_name=name if unit_type in ("monster", "npc") else "",
                        hp=hp, max_hp=hp, armor=int(p.get("armor", 5)),
                        ap=0, max_ap=0, gold=0,
                        vision_range=p.get("vision_range") or gs.room.config.vision_range,
                        listen_radius=p.get("listen_radius", 6),
                        passive_perception=p.get("passive_perception", 10),
                        darkvision=bool(p.get("darkvision", False)),
                        stealth=int(p.get("stealth", 0)),
                        is_shop=bool(p.get("is_shop", False)),
                        shop_items=list(p.get("shop_items") or []),
                    )
                    _log_event(gs, player_id, "place_unit", target=token_id, params=p)
                    await _broadcast_state(gs, room_id)
                elif t == "spawn_token":
                    # DM 从 Actor 库拖拽生成 Token
                    if not (user and user.is_admin):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "admin only"}
                        })
                        continue
                    actor_id = p.get("actor_id")
                    actor = user_storage.get_actor(actor_id)
                    if not actor:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "actor not found"}
                        })
                        continue
                    x, y = int(p.get("x", 0)), int(p.get("y", 0))
                    token_id = f"{actor['type']}_{int(time.time() * 1000) % 1000000}"
                    async with gs.lock:
                        gs.room.tokens[token_id] = Token(
                            id=token_id, type=actor["type"], actor_id=actor_id,
                            character_name=actor.get("name", ""),
                            position={"x": x, "y": y},
                            hp=actor["hp"], max_hp=actor["max_hp"],
                            armor=actor["armor"], ap=actor["ap"], max_ap=actor["max_ap"],
                            vision_range=actor["vision_range"],
                            darkvision=bool(actor["darkvision"]),
                            listen_radius=actor["listen_radius"],
                            passive_perception=actor["passive_perception"],
                            stealth=actor["stealth"],
                            equipment_slots=actor.get("equipment_slots") or [None]*6,
                            skill_slots=actor.get("skill_slots") or [None, None],
                            backpack=actor.get("backpack") or [],
                            avatar_url=actor.get("avatar_url"),
                            is_shop=bool(actor.get("is_shop", False)),
                            shop_items=actor.get("shop_items") or [],
                        )
                        gs.room.turn_order.append(token_id)
                        _log_event(gs, player_id, "spawn_token", target=token_id,
                                   params={"actor_id": actor_id, "x": x, "y": y})
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "rotate_token":
                    token = gs.room.tokens.get(p.get("token_id"))
                    if token and _can_control(token, user, player_id):
                        async with gs.lock:
                            token.facing = int(p.get("facing", 0)) % 8
                            _log_event(gs, player_id, "rotate_token",
                                       target=p.get("token_id"), params=p)
                            if gs.snapshot_storage:
                                gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "size_token":
                    token = gs.room.tokens.get(p.get("token_id"))
                    if token and _can_control(token, user, player_id):
                        async with gs.lock:
                            token.size = max(1, min(4, int(p.get("size", 1))))
                            _log_event(gs, player_id, "size_token",
                                       target=p.get("token_id"), params=p)
                            if gs.snapshot_storage:
                                gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "set_terrain":
                    async with gs.lock:
                        gs.map_svc.set_terrain(p.get("x"), p.get("y"), p.get("type", "flat"))
                        _log_event(gs, player_id, "set_terrain", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "set_cell_meta":
                    # 设置黑暗/光照等元数据（DM 笔刷）
                    x, y = int(p.get("x", 0)), int(p.get("y", 0))
                    async with gs.lock:
                        if "is_dark" in p:
                            gs.map_svc.set_dark(x, y, bool(p["is_dark"]))
                        if "light_radius" in p:
                            gs.map_svc.set_light(x, y, int(p["light_radius"]))
                        _log_event(gs, player_id, "set_cell_meta", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "fill_terrain":
                    async with gs.lock:
                        gs.map_svc.fill_area(
                            p.get("x1"), p.get("y1"), p.get("x2"), p.get("y2"),
                            p.get("type", "flat"),
                        )
                        _log_event(gs, player_id, "fill_terrain", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "resize_map":
                    w, h = p.get("width", 30), p.get("height", 30)
                    async with gs.lock:
                        gs.room.config = gs.room.config.model_copy(
                            update={"map_width": w, "map_height": h}
                        )
                        # Rebuild map (clears existing terrains — acceptable for MVP)
                        gs.game_map = GameMap(width=w, height=h)
                        gs.room.game_map = gs.game_map
                        gs.map_svc = MapService(gs.game_map)
                        gs.vision_svc = VisionService(gs.room, gs.game_map)
                        gs.token_svc = TokenService(gs.room, gs.game_map)
                        _log_event(gs, player_id, "resize_map", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "set_turn_order":
                    if not is_admin:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "only admin can set turn order"}
                        })
                        continue
                    order = p.get("order", [])
                    async with gs.lock:
                        gs.turn_svc.set_order(order)
                        _log_event(gs, player_id, "set_turn_order", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "shuffle_turn_order":
                    if not is_admin:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "only admin can shuffle turn order"}
                        })
                        continue
                    async with gs.lock:
                        gs.turn_svc.shuffle_order()
                        _log_event(gs, player_id, "shuffle_turn_order", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "force_set_actor":
                    if not is_admin:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "only admin can force set actor"}
                        })
                        continue
                    async with gs.lock:
                        gs.turn_svc.force_set_actor(p.get("token_id", ""))
                        _log_event(gs, player_id, "force_set_actor", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    gs.start_turn_timer(callback=lambda: _broadcast_state(gs, room_id))
                    await _broadcast_state(gs, room_id)
                elif t == "clear_combat_log":
                    if not is_admin:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "only admin can clear combat log"}
                        })
                        continue
                    async with gs.lock:
                        gs.event_log.clear()
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await connection_mgr.broadcast(room_id, {
                        "type": "combat_log_cleared", "payload": {}
                    })
                elif t == "set_fog_of_war":
                    if not is_admin:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "only admin can toggle fog of war"}
                        })
                        continue
                    enabled = p.get("enabled", True)
                    async with gs.lock:
                        gs.room.config = gs.room.config.model_copy(
                            update={"fog_of_war_enabled": enabled}
                        )
                        _log_event(gs, player_id, "set_fog_of_war", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "set_poison_circle":
                    if not is_admin:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "only admin can control poison circle"}
                        })
                        continue
                    async with gs.lock:
                        gs.turn_svc.set_poison_circle(
                            center_x=p.get("center_x"),
                            center_y=p.get("center_y"),
                            radius=p.get("radius"),
                            enabled=p.get("enabled"),
                        )
                        _log_event(gs, player_id, "set_poison_circle", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "attack":
                    # 攻击交互：目标选择 → 掷骰 → 命中判定 → 伤害计算 → 应用
                    attacker_id = p.get("attacker_id")
                    defender_id = p.get("defender_id")
                    attacker = gs.room.tokens.get(attacker_id)
                    defender = gs.room.tokens.get(defender_id)
                    if not attacker or not defender:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "attacker or defender not found"}
                        })
                        continue
                    if not _can_control(attacker, user, player_id):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "cannot control attacker"}
                        })
                        continue
                    # 注册默认攻击规则（如果还没有）
                    if attacker_id not in gs.combat_engine.rules:
                        gs._register_default_attack_rules(attacker)
                    # 执行攻击（锁内）
                    async with gs.lock:
                        context = CombatContext(
                            action="attack",
                            actor=attacker,
                            target=defender,
                            room_config=gs.room.config,
                        )
                        combat_log = gs.combat_engine.execute_action(context)
                        # 检查击杀
                        if defender.is_dead:
                            # 击杀积分
                            attacker.score += gs.room.config.score_kill
                            attacker.gold += gs.room.config.kill_drop_gold
                            # 记录淘汰顺序
                            gs.turn_svc.record_elimination(defender_id)
                            _log_event(gs, player_id, "kill", target=defender_id, params={"score": attacker.score})
                        _log_event(gs, player_id, "attack", target=defender_id, params=combat_log)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    # 广播战斗结果（锁外）
                    await connection_mgr.broadcast(room_id, {
                        "type": "combat_log",
                        "payload": combat_log,
                    })
                    await _broadcast_state(gs, room_id)
                elif t == "defend":
                    # 防御：消耗1AP，进行察觉检定
                    token_id = p.get("token_id")
                    token = gs.room.tokens.get(token_id)
                    if not token or not _can_control(token, user, player_id):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "cannot control token"}
                        })
                        continue
                    if token.ap < gs.room.config.defend_ap_cost:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "AP不足"}
                        })
                        continue
                    async with gs.lock:
                        token.ap -= gs.room.config.defend_ap_cost
                        # 察觉检定：D20 + 被动觉察
                        r = roll_dice(sides=20, modifier=token.passive_perception - 10)
                        _log_event(gs, player_id, "defend", target=token_id, params={"roll": r.model_dump(), "ap_after": token.ap})
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await connection_mgr.broadcast(room_id, {
                        "type": "defend_result",
                        "payload": {"token_id": token_id, "roll": r.model_dump(), "ap_after": token.ap},
                    })
                    await _broadcast_state(gs, room_id)
                elif t == "sprint":
                    # 疾跑：消耗2AP，移动4格
                    token_id = p.get("token_id")
                    path = p.get("path", [])
                    token = gs.room.tokens.get(token_id)
                    if not token or not _can_control(token, user, player_id):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "cannot control token"}
                        })
                        continue
                    if token.ap < gs.room.config.sprint_ap_cost:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "AP不足（疾跑需2AP）"}
                        })
                        continue
                    if len(path) > gs.room.config.sprint_distance:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": f"疾跑最多{gs.room.config.sprint_distance}格"}
                        })
                        continue
                    async with gs.lock:
                        token.ap -= gs.room.config.sprint_ap_cost
                        result = gs.token_svc.move_along_path(token_id, [tuple(x) for x in path])
                        _log_event(gs, player_id, "sprint", target=token_id, params={"path": path, "ap_after": token.ap})
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "use_item":
                    # 使用道具/技能
                    token_id = p.get("token_id")
                    item_name = p.get("item_name", "")
                    token = gs.room.tokens.get(token_id)
                    if not token or not _can_control(token, user, player_id):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "cannot control token"}
                        })
                        continue
                    # 检查道具是否在装备槽或背包中
                    in_slot = item_name in (token.equipment_slots or [])
                    in_backpack = item_name in (token.backpack or [])
                    if not in_slot and not in_backpack:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "道具不在装备栏或背包中"}
                        })
                        continue
                    # 检查次数
                    charges = token.item_charges.get(item_name)
                    if charges is not None and charges <= 0:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "道具次数已耗尽"}
                        })
                        continue
                    async with gs.lock:
                        # 扣除次数或从背包移除
                        if in_backpack and item_name in token.backpack:
                            if charges is not None:
                                token.item_charges[item_name] -= 1
                            else:
                                token.backpack.remove(item_name)
                        elif in_slot and charges is not None:
                            token.item_charges[item_name] -= 1
                        # 广播事件让团主知道谁用了什么，效果由团主口胡（ADR-5）
                        _log_event(gs, player_id, "use_item", target=token_id, params={"item": item_name})
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await connection_mgr.broadcast(room_id, {
                        "type": "item_used",
                        "payload": {"token_id": token_id, "item": item_name},
                    })
                    await _broadcast_state(gs, room_id)
                elif t == "buy_item":
                    # 跟商店型 NPC 买道具：扣买家金币，把道具加进背包。
                    buyer_id = p.get("buyer_token_id")
                    shop_id = p.get("shop_token_id")
                    item_name = p.get("item_name", "")
                    buyer = gs.room.tokens.get(buyer_id)
                    shop = gs.room.tokens.get(shop_id)
                    if not buyer or not _can_control(buyer, user, player_id):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "无法操作这个角色"}
                        })
                        continue
                    if not shop or not shop.is_shop:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "这不是一个商店"}
                        })
                        continue
                    if item_name not in (shop.shop_items or []):
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "这家店没有这个道具"}
                        })
                        continue
                    item = user_storage.get_item_by_name(item_name)
                    if not item or item["price"] <= 0:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": "该道具未设置价格，不能购买"}
                        })
                        continue
                    if buyer.gold < item["price"]:
                        await connection_mgr.send_to_player(room_id, player_id, {
                            "type": "error", "payload": {"message": f"金币不足（需要{item['price']}，你有{buyer.gold}）"}
                        })
                        continue
                    async with gs.lock:
                        buyer.gold -= item["price"]
                        buyer.backpack.append(item_name)
                        _log_event(gs, player_id, "buy_item", target=buyer_id,
                                   params={"shop": shop_id, "item": item_name, "price": item["price"]})
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await connection_mgr.broadcast(room_id, {
                        "type": "item_bought",
                        "payload": {"token_id": buyer_id, "item": item_name, "price": item["price"]},
                    })
                    await _broadcast_state(gs, room_id)
                elif t == "end_turn":
                    async with gs.lock:
                        gs.cancel_turn_timer()
                        gs.turn_svc.end_turn()
                        _log_event(gs, player_id, "end_turn")
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    # 启动下一回合的倒计时
                    gs.start_turn_timer(callback=lambda: _broadcast_state(gs, room_id))
                    await _broadcast_state(gs, room_id)
                elif t == "set_turn_order":
                    async with gs.lock:
                        gs.turn_svc.set_order(p.get("order", []))
                        _log_event(gs, player_id, "set_turn_order", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "shuffle_turn_order":
                    async with gs.lock:
                        gs.turn_svc.shuffle_order(p.get("order"))
                        _log_event(gs, player_id, "shuffle_turn_order", params=p)
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    await _broadcast_state(gs, room_id)
                elif t == "start_game":
                    async with gs.lock:
                        gs.turn_svc.start()
                        _log_event(gs, player_id, "start_game")
                        if gs.snapshot_storage:
                            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
                    gs.start_turn_timer(callback=lambda: _broadcast_state(gs, room_id))
                    await _broadcast_state(gs, room_id)
                elif t == "get_ranking":
                    # Phase 2: 查询当前排名
                    ranking = gs.turn_svc.compute_final_ranking()
                    await connection_mgr.send_to_player(room_id, player_id, {
                        "type": "ranking",
                        "payload": {
                            "ranking": ranking,
                            "elimination_order": gs.room.elimination_order,
                        },
                    })
                else:
                    await connection_mgr.send_to_player(room_id, player_id, {
                        "type": "error", "payload": {"message": f"unknown type: {t}"}
                    })
            except WebSocketDisconnect:
                raise
            except Exception as e:
                await connection_mgr.send_to_player(room_id, player_id, {
                    "type": "error", "payload": {"message": f"操作处理失败: {e}"}
                })
    except WebSocketDisconnect:
        connection_mgr.disconnect(room_id, player_id)
        if player_id in room.players:
            room.players[player_id].is_connected = False


def _can_control(token, user, player_id: str) -> bool:
    """权限：管理员可操作任意 token；玩家只能操作 owner_id 匹配自己的。"""
    if user and getattr(user, "is_admin", False):
        return True
    owner = getattr(token, "owner_id", None)
    return owner == player_id


async def _broadcast_state(gs: RoomGameState, room_id: str):
    """对所有连接的玩家广播，按各自视野定制 payload。"""
    for pid in connection_mgr.players_in_room(room_id):
        await _send_state_to_player(gs, room_id, pid)


_SECRET_FIELDS = ("backpack", "item_charges", "skill_slots")


def _strip_secret_fields(tk_data: dict) -> dict:
    """裁剪其他玩家不可见的字段（背包/道具次数/技能）。
    设计文档 §7.1: 装备栏可见，背包/技能完全隐藏。
    """
    d = dict(tk_data)  # shallow copy
    if "backpack" in d:
        d["backpack"] = []
    if "item_charges" in d:
        d["item_charges"] = {}
    if "skill_slots" in d:
        d["skill_slots"] = [None, None]
    return d


async def _send_state_to_player(gs: RoomGameState, room_id: str, player_id: str):
    """按玩家定制 state_sync：
    - 管理员：完整 room
    - 玩家：仅可见 token + visible_cells + detected_tokens
    """
    is_admin = connection_mgr.is_admin(room_id, player_id)
    if is_admin:
        payload = gs.room.model_dump()
        payload["turn_deadline"] = gs.turn_deadline
        await connection_mgr.send_to_player(room_id, player_id, {
            "type": "state_sync",
            "payload": payload,
            "is_admin": True,
        })
        return

    # 玩家：找到自己的 token
    pid = player_id
    player = gs.room.players.get(pid)
    tid = player.token_id if player else None
    token = gs.room.tokens.get(tid) if tid else None

    base = gs.room.model_dump()
    base["turn_deadline"] = gs.turn_deadline  # Phase 2: 回合倒计时

    if not token or not token.position:
        # 未落子：看全图静态地形，但隐藏所有动态 token 细节（只留自己的）
        filtered_tokens = {}
        if tid and tid in base["tokens"]:
            filtered_tokens[tid] = base["tokens"][tid]
        base["tokens"] = filtered_tokens
        # visible_cells 留空：前端据此显示全图（未参战不该被迷雾困住）
        await connection_mgr.send_to_player(room_id, player_id, {
            "type": "state_sync", "payload": base,
        })
        return

    # 计算视野
    if not getattr(gs.room.config, 'fog_of_war_enabled', True):
        # 战争迷雾关闭：所有玩家看全图，但仍然裁剪其他玩家的背包/技能
        base_tokens = base["tokens"]
        base["tokens"] = {
            tk_id: (tk_data if tk_id == tid else _strip_secret_fields(tk_data))
            for tk_id, tk_data in base_tokens.items()
        }
        await connection_mgr.send_to_player(room_id, player_id, {
            "type": "state_sync", "payload": base,
        })
        return

    visible_cells = gs.vision_svc.compute_visible_cells(tid)
    visible_token_ids = set(gs.vision_svc.compute_visible_tokens(tid))
    detected = gs.vision_svc.compute_detected_tokens(tid)

    # 过滤 tokens：可见的完整下发；被觉察的只下发 {id, type, character_name}；
    # 其余一律不下发
    filtered_tokens = {}
    for tk_id, tk_data in base["tokens"].items():
        if tk_id == tid:
            filtered_tokens[tk_id] = tk_data  # 自己永远可见
        elif tk_id in visible_token_ids:
            # 视野内可见：装备栏可见，但背包/技能/道具次数隐藏
            filtered_tokens[tk_id] = _strip_secret_fields(tk_data)
        elif tk_id in detected:
            # 只露方位，不露坐标/HP/装备
            filtered_tokens[tk_id] = {
                "id": tk_id,
                "type": tk_data.get("type", "monster"),
                "character_name": tk_data.get("character_name", "?"),
            }
    base["tokens"] = filtered_tokens

    # 过滤 game_map 地形：不可见格只留坐标，清空类型/黑暗/光照（防 F12 偷看）
    if base.get("game_map") and base["game_map"].get("terrain"):
        vis_set = visible_cells
        for row in base["game_map"]["terrain"]:
            for cell in row:
                if (cell["x"], cell["y"]) not in vis_set:
                    cell["type"] = "flat"
                    cell["is_smoke"] = False
                    cell["smoke_ttl"] = None
                    cell["is_dark"] = False
                    cell["light_radius"] = 0
                    cell["height"] = 0

    base["visible_cells"] = [[x, y] for (x, y) in sorted(visible_cells)]
    base["detected_tokens"] = detected

    await connection_mgr.send_to_player(room_id, player_id, {
        "type": "state_sync", "payload": base,
    })
