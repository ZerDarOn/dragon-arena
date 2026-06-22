import pytest
from app.services.chat_service import ChatService
from app.schemas.room import Room, Token
from app.schemas.map import GameMap


@pytest.fixture
def setup():
    room = Room(id="r1", name="test")
    room.tokens["t1"] = Token(id="t1", owner_id="p1", position={"x": 5, "y": 5})
    room.tokens["t2"] = Token(id="t2", owner_id="p2", position={"x": 6, "y": 5})
    room.tokens["t3"] = Token(id="t3", owner_id="p3", position={"x": 15, "y": 15})
    game_map = GameMap(width=20, height=20)
    svc = ChatService(room, game_map)
    return svc, room


def test_hall_broadcast(setup):
    svc, room = setup
    msg = svc.send("p1", "hall", text="hello")
    assert msg.recipients is None


def test_private(setup):
    svc, room = setup
    msg = svc.send("p1", "private", text="secret", target_player="p2")
    assert msg.recipients == ["p1", "p2"]


def test_spatial_normal_reaches_nearby(setup):
    svc, room = setup
    msg = svc.send("p1", "spatial_normal", text="hi")
    assert "p2" in msg.recipients
    assert "p3" not in msg.recipients


def test_spatial_shout_reaches_far(setup):
    svc, room = setup
    msg = svc.send("p1", "spatial_shout", text="HELP!")
    assert "p2" in msg.recipients
    assert "p3" in msg.recipients  # dist 10 <= shout radius 12


def test_spatial_blocked_by_wall(setup):
    svc, room = setup
    from app.services.map_service import MapService
    room.tokens["t2"].position = {"x": 8, "y": 5}
    MapService(svc.map).set_terrain(7, 5, "wall")
    msg = svc.send("p1", "spatial_normal", text="hi")
    assert "p2" not in msg.recipients


def test_dead_cannot_speak_spatial(setup):
    svc, room = setup
    room.tokens["t1"].is_dead = True
    msg = svc.send("p1", "spatial_normal", text="hi")
    assert msg is None


def test_dead_cannot_hear_spatial(setup):
    svc, room = setup
    room.tokens["t2"].is_dead = True
    msg = svc.send("p1", "spatial_normal", text="hi")
    assert "p2" not in msg.recipients
