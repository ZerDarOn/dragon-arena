from app.services.map_service import MapService
from app.schemas.map import GameMap


def test_set_terrain():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_terrain(3, 4, "wall")
    assert m.terrain[4][3].type == "wall"


def test_set_terrain_out_of_bounds():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_terrain(99, 99, "wall")
    assert m.terrain[0][0].type == "flat"


def test_fill_area():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.fill_area(2, 2, 4, 4, "grass")
    for y in range(2, 5):
        for x in range(2, 5):
            assert m.terrain[y][x].type == "grass"


def test_clear_terrain():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_terrain(3, 3, "wall")
    svc.clear_terrain(3, 3)
    assert m.terrain[3][3].type == "flat"


def test_set_height():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_height(2, 2, 1)
    assert m.terrain[2][2].height == 1


def test_set_smoke():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_smoke(2, 2, ttl=3)
    assert m.terrain[2][2].is_smoke is True
    assert m.terrain[2][2].smoke_ttl == 3


def test_decrement_smoke():
    m = GameMap(width=10, height=10)
    svc = MapService(m)
    svc.set_smoke(2, 2, ttl=2)
    svc.tick_smoke()
    assert m.terrain[2][2].smoke_ttl == 1
    assert m.terrain[2][2].is_smoke is True
    svc.tick_smoke()
    assert m.terrain[2][2].smoke_ttl is None
    assert m.terrain[2][2].is_smoke is False
