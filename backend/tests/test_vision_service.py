import pytest
from app.services.vision_service import VisionService
from app.schemas.room import Room, Token
from app.schemas.map import GameMap


@pytest.fixture
def setup():
    room = Room(id="r1", name="test")
    room.tokens["t1"] = Token(
        id="t1", owner_id="p1",
        position={"x": 5, "y": 5}, facing=0, vision_range=6,
    )
    game_map = GameMap(width=20, height=20)
    svc = VisionService(room, game_map)
    return svc, room


def test_visible_cell_in_front(setup):
    svc, room = setup
    vis = svc.compute_visible_cells("t1")
    assert (5, 2) in vis


def test_wall_blocks_vision(setup):
    svc, room = setup
    from app.services.map_service import MapService
    MapService(svc.map).set_terrain(5, 3, "wall")
    vis = svc.compute_visible_cells("t1")
    assert (5, 1) not in vis


def test_behind_not_visible(setup):
    svc, room = setup
    vis = svc.compute_visible_cells("t1")
    assert (5, 8) not in vis


def test_visibility_for_other_token(setup):
    svc, room = setup
    room.tokens["t2"] = Token(id="t2", position={"x": 5, "y": 2})
    visible_tokens = svc.compute_visible_tokens("t1")
    assert "t2" in visible_tokens


def test_token_behind_wall_invisible(setup):
    svc, room = setup
    from app.services.map_service import MapService
    MapService(svc.map).set_terrain(5, 3, "wall")
    room.tokens["t2"] = Token(id="t2", position={"x": 5, "y": 1})
    visible_tokens = svc.compute_visible_tokens("t1")
    assert "t2" not in visible_tokens
