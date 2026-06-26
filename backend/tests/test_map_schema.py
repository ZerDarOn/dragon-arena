from app.schemas.map import GameMap, TerrainCell


def test_terrain_cell_defaults():
    c = TerrainCell(x=1, y=2)
    assert c.x == 1
    assert c.y == 2
    assert c.terrain_type == "flat"
    assert c.blocks_movement is False
    assert c.blocks_vision is False
    assert c.height == 0
    assert c.is_smoke is False


def test_game_map_dimensions():
    m = GameMap(width=20, height=20)
    assert m.width == 20
    assert m.height == 20
    assert len(m.terrain) == 20
    assert len(m.terrain[0]) == 20
    assert m.terrain[0][0].terrain_type == "flat"


def test_safe_zone():
    m = GameMap(width=30, height=30)
    assert m.safe_zone["center"] == {"x": 15, "y": 15}
    assert m.safe_zone["radius"] == 15
