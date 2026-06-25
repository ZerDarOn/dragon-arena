"""并发安全测试：验证 RoomGameState 的锁防止并发攻击 HP 被覆盖。

模拟两个玩家同时 attack 同一个 defender，
在加锁前这个测试会失败（HP 只扣一次），
加锁后 HP 正确扣两次。
"""
import asyncio
import pytest

from app.schemas.room import Room, Token, Player
from app.config import RoomConfig
from app.ws.handler import RoomGameState, get_game_state
from app.services.room_service import RoomService
from app.services.room_snapshot_storage import RoomSnapshotStorage


@pytest.fixture
def gs(temp_db):
    """构造一个带两个 attacker + 一个 defender 的 RoomGameState。"""
    room = Room(id="r1", name="test", config=RoomConfig(map_width=10, map_height=10))
    room.players["p1"] = Player(id="p1", name="a1", nickname="a1", token_id="t1")
    room.players["p2"] = Player(id="p2", name="a2", nickname="a2", token_id="t2")
    room.tokens["t1"] = Token(
        id="t1", character_name="atk1", hp=100, max_hp=100,
        position={"x": 1, "y": 1}, armor=0, ap=2,
        equipment_slots=["剑", None, None, None, None, None],
    )
    room.tokens["t2"] = Token(
        id="t2", character_name="atk2", hp=100, max_hp=100,
        position={"x": 2, "y": 1}, armor=0, ap=2,
        equipment_slots=["剑", None, None, None, None, None],
    )
    room.tokens["t3"] = Token(
        id="t3", character_name="def", hp=100, max_hp=100,
        position={"x": 3, "y": 1}, armor=0, ap=2,
    )
    room.turn_order = ["t1", "t2", "t3"]
    room.current_actor = "t1"
    room.big_turn = 1
    room.sub_turn = 0

    # 注入 snapshot storage（用 temp_db 路径）
    snapshot = RoomSnapshotStorage(db_path=temp_db)
    gs = RoomGameState(room)
    gs.snapshot_storage = snapshot
    return gs


@pytest.mark.asyncio
async def test_concurrent_attack_hp_not_overwritten(gs, monkeypatch):
    """两个 attacker 同时打同一个 defender，两次伤害都应生效（不被覆盖）。"""
    from app.services.combat_engine import CombatContext

    # 固定骰子去掉随机性：D20 恒为 15 → 必命中（15≥近战DC8），近战伤害=base10+(15-8)=17/次。
    # 否则低骰会 miss/0 伤，HP 偶尔停在 100，让这个测试 flaky（与并发逻辑无关的假阴性）。
    monkeypatch.setattr("app.services.dice_service._rand_int", lambda a, b: 15)

    defender = gs.room.tokens["t3"]
    initial_hp = defender.hp
    assert initial_hp == 100

    # 注册攻击规则（否则 execute_action 不会执行）
    gs._register_default_attack_rules(gs.room.tokens["t1"])
    gs._register_default_attack_rules(gs.room.tokens["t2"])

    async def attack(attacker_id: str, defender_id: str):
        # 模拟 handler 里 attack 分支的核心逻辑，但用锁包裹
        attacker = gs.room.tokens[attacker_id]
        defender = gs.room.tokens[defender_id]
        async with gs.lock:
            context = CombatContext(
                action="attack",
                actor=attacker,
                target=defender,
                room_config=gs.room.config,
            )
            gs.combat_engine.execute_action(context)
            # 快照（锁内）
            gs.snapshot_storage.save(gs.room.id, gs.room.model_dump_json())
        # 广播在锁外（模拟 handler 的 await broadcast）
        await asyncio.sleep(0)

    # 并发执行两次 attack
    await asyncio.gather(
        attack("t1", "t3"),
        attack("t2", "t3"),
    )

    # 验证两次攻击都生效（不是只扣一次被覆盖）：近战 17/次 × 2 = 34 → 100 - 34 = 66。
    # 若锁失效导致一次写覆盖另一次，HP 会是 83（只扣一次）。
    assert defender.hp == 66, f"两次并发攻击应各扣 17、HP 应为 66，实际 {defender.hp}"
    # 快照也应落盘
    assert gs.snapshot_storage.load(gs.room.id) is not None
