from typing import Tuple, List
import math


Point = Tuple[int, int]


def chebyshev_distance(a: Point, b: Point) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def manhattan_distance(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def bresenham_line(start: Point, end: Point) -> List[Point]:
    """Bresenham line algorithm, returns cells between start and end inclusive."""
    x0, y0 = start
    x1, y1 = end
    cells = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    sx = -1 if x0 > x1 else 1
    sy = -1 if y0 > y1 else 1
    if dx > dy:
        err = dx / 2.0
        while x != x1:
            cells.append((x, y))
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != y1:
            cells.append((x, y))
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
    cells.append((x, y))
    return cells


def angle_to_direction(dx: int, dy: int) -> int:
    """Convert (dx,dy) to 0-7 direction (0=N, clockwise).
    Grid convention: x=column (east positive), y=row (south positive).
    North = -y direction.
    """
    if dx == 0 and dy == 0:
        return 0
    angle = math.degrees(math.atan2(dx, -dy))
    if angle < 0:
        angle += 360
    return int(round(angle / 45)) % 8


def is_in_sector(origin: Point, facing: int, target: Point, max_radius: int) -> bool:
    """Check if target is in the visible sector of origin.
    Facing: 0=N,1=NE,2=E,3=SE,4=S,5=SW,6=W,7=NW
    Front ±45°: fully visible up to max_radius
    Sides ±90°: visible up to 3 cells (hardcoded for now, will be configurable)
    Behind: not visible
    """
    dist = chebyshev_distance(origin, target)
    if dist == 0:
        return True
    if dist > max_radius:
        return False
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    target_dir = angle_to_direction(dx, dy)
    diff = (target_dir - facing) % 8
    if diff in (0, 1, 7):
        return dist <= max_radius
    elif diff in (2, 6):
        return dist <= min(3, max_radius)
    else:
        return False


def has_wall_between(game_map, a: Point, b: Point) -> bool:
    """Check if any solid wall cell lies on the line between a and b (exclusive).
    语义 = 实体墙（blocks_movement AND blocks_vision），声音穿玻璃/烟雾/水。"""
    cells = bresenham_line(a, b)
    for (x, y) in cells[1:-1]:
        if 0 <= y < game_map.height and 0 <= x < game_map.width:
            cell = game_map.terrain[y][x]
            # 实体墙 = 两布尔都 True（is_sound_blocking 语义）
            if cell.blocks_movement and cell.blocks_vision:
                return True
    return False
