"""攻击时玩家声明的修正值应计入命中总值。"""
from app.schemas.room import Room, Token
from app.config import RoomConfig
from app.services.combat_engine import CombatContext
from app.ws.handler import RoomGameState


def test_attack_modifier_boosts_hit(monkeypatch):
    monkeypatch.setattr("app.services.dice_service._rand_int", lambda a, b: 5)  # D20=5
    room = Room(id="r", name="t", config=RoomConfig(map_width=10, map_height=10))
    room.tokens["a"] = Token(id="a", hp=100, max_hp=100, position={"x": 1, "y": 1},
                             armor=0, ap=5, equipment_slots=["剑", None, None, None, None, None])
    room.tokens["d"] = Token(id="d", hp=100, max_hp=100, position={"x": 2, "y": 1}, armor=0, ap=2)
    gs = RoomGameState(room)
    gs._register_default_attack_rules(room.tokens["a"])
    # 不带修正：D20=5 < 近战DC8 → 未命中
    ctx0 = CombatContext(action="attack", actor=room.tokens["a"], target=room.tokens["d"], room_config=room.config)
    gs.combat_engine.execute_action(ctx0)
    assert ctx0.hit_result.is_hit is False
    # 带 +10 修正：5+10=15 ≥ 8 → 命中，且 total 含修正
    ctx1 = CombatContext(action="attack", actor=room.tokens["a"], target=room.tokens["d"],
                         room_config=room.config, attack_bonus=10)
    gs.combat_engine.execute_action(ctx1)
    assert ctx1.hit_result.is_hit is True
    assert ctx1.hit_result.total == ctx1.hit_result.roll + ctx1.hit_result.bonus
    assert ctx1.hit_result.bonus >= 10
