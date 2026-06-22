from app.schemas.room import Room, Player, Token, StateTag
from app.config import RoomConfig


def test_create_room_defaults():
    room = Room(id="r1", name="Dragon#1")
    assert room.name == "Dragon#1"
    assert room.config == RoomConfig()
    assert room.players == {}
    assert room.current_actor is None
    assert room.turn_order == []


def test_token_defaults():
    t = Token(id="t1", owner_id="p1")
    assert t.hp == 100
    assert t.armor == 5
    assert t.ap == 2
    assert t.max_ap == 2
    assert t.facing == 0
    assert t.is_dead is False
    assert t.is_hidden is False
    assert t.position is None


def test_state_tag():
    s = StateTag(id="s1", name="中毒", description="每回合扣3点", ttl=3, intensity=3)
    assert s.ttl == 3
    assert s.intensity == 3
