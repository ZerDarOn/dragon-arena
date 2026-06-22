from app.services.geometry_service import (
    chebyshev_distance, manhattan_distance,
    is_in_sector, bresenham_line, has_wall_between,
)
from app.schemas.map import GameMap


def test_chebyshev():
    assert chebyshev_distance((0, 0), (3, 4)) == 4
    assert chebyshev_distance((1, 1), (1, 1)) == 0


def test_manhattan():
    assert manhattan_distance((0, 0), (3, 4)) == 7


def test_bresenham_simple():
    cells = bresenham_line((0, 0), (3, 0))
    assert (0, 0) in cells
    assert (3, 0) in cells
    assert len(cells) == 4


def test_bresenham_diagonal():
    cells = bresenham_line((0, 0), (3, 3))
    assert (0, 0) in cells
    assert (3, 3) in cells


def test_is_in_sector_front():
    # facing 0 = north, target directly north = in front
    assert is_in_sector(origin=(5, 5), facing=0, target=(5, 2), max_radius=6) is True


def test_is_in_sector_behind():
    # facing 0 = north, target south = behind
    assert is_in_sector(origin=(5, 5), facing=0, target=(5, 8), max_radius=6) is False


def test_is_in_sector_beyond_range():
    assert is_in_sector(origin=(5, 5), facing=0, target=(5, 0), max_radius=4) is False


def test_has_wall_between_clear():
    m = GameMap(width=10, height=10)
    assert has_wall_between(m, (0, 0), (5, 0)) is False


def test_has_wall_between_blocked():
    m = GameMap(width=10, height=10)
    m.terrain[0][3].type = "wall"
    assert has_wall_between(m, (0, 0), (5, 0)) is True
