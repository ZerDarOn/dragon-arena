import pytest
from app.services.token_service import TokenService
from app.schemas.room import Room, Token
from app.schemas.map import GameMap


@pytest.fixture
def setup():
    room = Room(id="r1", name="test")
    room.tokens["t1"] = Token(id="t1", owner_id="p1", position={"x": 5, "y": 5}, facing=0)
    game_map = GameMap(width=10, height=10)
    svc = TokenService(room, game_map)
    return svc, room


def test_place_token(setup):
    svc, room = setup
    svc.place_token("t2", 3, 3)
    assert room.tokens["t2"].position == {"x": 3, "y": 3}


def test_place_token_occupied(setup):
    svc, room = setup
    result = svc.place_token("t2", 5, 5)
    assert result is False


def test_move_path_success(setup):
    svc, room = setup
    result = svc.move_along_path("t1", [(6, 5), (7, 5)])
    assert result.success is True
    assert room.tokens["t1"].position == {"x": 7, "y": 5}
    assert room.tokens["t1"].facing == 2  # east
    assert room.tokens["t1"].ap == 0


def test_move_path_through_wall(setup):
    svc, room = setup
    from app.services.map_service import MapService
    MapService(svc.map).set_terrain(6, 5, "wall")
    result = svc.move_along_path("t1", [(6, 5), (7, 5)])
    assert result.success is False
    assert "wall" in result.reason.lower()


def test_move_path_insufficient_ap(setup):
    svc, room = setup
    room.tokens["t1"].ap = 1
    result = svc.move_along_path("t1", [(6, 5), (7, 5)])
    assert result.success is False
    assert "ap" in result.reason.lower()


def test_move_empty_path_keeps_facing(setup):
    svc, room = setup
    room.tokens["t1"].facing = 4
    result = svc.move_along_path("t1", [])
    assert result.success is True
    assert room.tokens["t1"].facing == 4


def test_modify_value(setup):
    svc, room = setup
    svc.modify_value("t1", "hp", -10)
    assert room.tokens["t1"].hp == 90


def test_modify_value_clamp(setup):
    svc, room = setup
    svc.modify_value("t1", "hp", -9999)
    assert room.tokens["t1"].hp == 0
    assert room.tokens["t1"].is_dead is True


def test_add_state(setup):
    svc, room = setup
    svc.add_state("t1", state_id="s1", name="中毒", description="扣血", ttl=3, intensity=3)
    assert len(room.tokens["t1"].states) == 1
    assert room.tokens["t1"].states[0].name == "中毒"
