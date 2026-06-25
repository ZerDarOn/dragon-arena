from app.schemas.map import GameMap


class MapService:
    def __init__(self, game_map: GameMap):
        self.map = game_map

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.map.width and 0 <= y < self.map.height

    def set_terrain(self, x: int, y: int, terrain_type: str) -> None:
        if not self._in_bounds(x, y):
            return
        self.map.terrain[y][x].type = terrain_type

    def fill_area(self, x1: int, y1: int, x2: int, y2: int, terrain_type: str) -> None:
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                self.set_terrain(x, y, terrain_type)

    def clear_terrain(self, x: int, y: int) -> None:
        self.set_terrain(x, y, "flat")
        if self._in_bounds(x, y):
            self.map.terrain[y][x].height = 0
            self.map.terrain[y][x].is_smoke = False
            self.map.terrain[y][x].smoke_ttl = None
            self.map.terrain[y][x].is_dark = False
            self.map.terrain[y][x].light_radius = 0

    def set_dark(self, x: int, y: int, is_dark: bool = True) -> None:
        if not self._in_bounds(x, y):
            return
        self.map.terrain[y][x].is_dark = is_dark

    def set_darkness_strength(self, x: int, y: int, strength: float) -> None:
        if not self._in_bounds(x, y):
            return
        self.map.terrain[y][x].darkness_strength = max(0.0, min(1.0, strength))

    def set_light(self, x: int, y: int, radius: int) -> None:
        """设光源：radius>0 点亮周围，radius=0 移除光源"""
        if not self._in_bounds(x, y):
            return
        self.map.terrain[y][x].light_radius = radius

    def set_height(self, x: int, y: int, h: int) -> None:
        if not self._in_bounds(x, y):
            return
        self.map.terrain[y][x].height = h

    def set_smoke(self, x: int, y: int, ttl: int) -> None:
        if not self._in_bounds(x, y):
            return
        self.map.terrain[y][x].is_smoke = True
        self.map.terrain[y][x].smoke_ttl = ttl

    def tick_smoke(self) -> None:
        for row in self.map.terrain:
            for cell in row:
                if cell.is_smoke and cell.smoke_ttl is not None:
                    cell.smoke_ttl -= 1
                    if cell.smoke_ttl <= 0:
                        cell.is_smoke = False
                        cell.smoke_ttl = None

    def is_wall(self, x: int, y: int) -> bool:
        if not self._in_bounds(x, y):
            return True
        return self.map.terrain[y][x].type == "wall"

    def is_smoke(self, x: int, y: int) -> bool:
        if not self._in_bounds(x, y):
            return False
        return self.map.terrain[y][x].is_smoke
