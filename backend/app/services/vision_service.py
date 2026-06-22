from typing import Set, List
from app.schemas.room import Room
from app.schemas.map import GameMap
from app.services.geometry_service import (
    chebyshev_distance, is_in_sector, bresenham_line, angle_to_direction,
)
from app.services.map_service import MapService


class VisionService:
    def __init__(self, room: Room, game_map: GameMap):
        self.room = room
        self.map = game_map
        self.map_svc = MapService(game_map)
        self.cfg = room.config

    def compute_visible_cells(self, token_id: str) -> Set[tuple]:
        token = self.room.tokens.get(token_id)
        if not token or not token.position:
            return set()
        origin = (token.position["x"], token.position["y"])
        vr = token.vision_range
        visible = {origin}
        for y in range(self.map.height):
            for x in range(self.map.width):
                target = (x, y)
                if target == origin:
                    continue
                if not is_in_sector(origin, token.facing, target, vr):
                    continue
                if self._is_blocked(origin, target):
                    continue
                visible.add(target)
        return visible

    def _is_blocked(self, a: tuple, b: tuple) -> bool:
        cells = bresenham_line(a, b)
        for (x, y) in cells[1:-1]:
            if self.map_svc.is_wall(x, y):
                return True
            if self.map_svc.is_smoke(x, y):
                return True
        return False

    def compute_visible_tokens(self, token_id: str) -> List[str]:
        token = self.room.tokens.get(token_id)
        if not token or not token.position:
            return []
        visible_cells = self.compute_visible_cells(token_id)
        result = []
        for other_id, other in self.room.tokens.items():
            if other_id == token_id or other.is_dead or not other.position:
                continue
            if other.is_hidden:
                continue
            pos = (other.position["x"], other.position["y"])
            if pos in visible_cells:
                result.append(other_id)
        return result

    def compute_direction_aware_targets(self, token_id: str) -> dict:
        token = self.room.tokens.get(token_id)
        if not token or not token.position:
            return {}
        origin = (token.position["x"], token.position["y"])
        vr = token.vision_range
        names = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        result = {}
        for other_id, other in self.room.tokens.items():
            if other_id == token_id or other.is_dead or not other.position or other.is_hidden:
                continue
            pos = (other.position["x"], other.position["y"])
            dist = chebyshev_distance(origin, pos)
            if vr < dist <= vr * 2 and not self._is_blocked(origin, pos):
                dx, dy = pos[0] - origin[0], pos[1] - origin[1]
                result[other_id] = names[angle_to_direction(dx, dy)]
        return result
