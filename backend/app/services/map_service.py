from app.schemas.map import GameMap


class MapService:
    def __init__(self, game_map: GameMap):
        self.map = game_map

    def _in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.map.width and 0 <= y < self.map.height

    # ─── 预设地形表（§3.2） ───
    PRESET_MAP = {
        "flat": {"terrain_type": "flat", "blocks_movement": False, "blocks_vision": False, "wall_render": None},
        "grass": {"terrain_type": "grass"},
        "dirt": {"terrain_type": "dirt"},
        "stone": {"terrain_type": "stone"},
        "sand": {"terrain_type": "sand"},
        "wood": {"terrain_type": "wood"},
        "ice": {"terrain_type": "ice"},
        "water": {"terrain_type": "water"},
        "water_deep": {"terrain_type": "water", "wall_render": "water_deep"},
        "lava": {"terrain_type": "lava", "blocks_movement": True, "wall_render": "lava"},
        "poison": {"terrain_type": "poison", "blocks_movement": True},
        "wall": {"terrain_type": "stone", "blocks_movement": True, "blocks_vision": True, "wall_render": "solid"},
        "door": {"terrain_type": "wood", "blocks_movement": True, "blocks_vision": True, "wall_render": "door"},
        "glass_wall": {"terrain_type": "glass", "blocks_vision": True, "wall_render": "glass"},
    }

    def set_terrain(self, x: int, y: int, terrain_type: str) -> None:
        """旧接口兼容：按 terrain_type 设置，保留旧调用方。
        新代码请用 paint_cell（支持 preset + 全字段）。"""
        if not self._in_bounds(x, y):
            return
        # 兼容旧 type 值
        if terrain_type in ("flat", "wall", "grass", "water", "high"):
            preset = self.PRESET_MAP.get(terrain_type, {})
        else:
            preset = {"terrain_type": terrain_type}
        self._apply_cell_update(x, y, preset)

    def _apply_cell_update(self, x: int, y: int, updates: dict) -> None:
        """底层：按字段更新格子。"""
        if not self._in_bounds(x, y):
            return
        cell = self.map.terrain[y][x]
        for k, v in updates.items():
            if hasattr(cell, k):
                setattr(cell, k, v)

    def paint_cell(self, x: int, y: int, *, preset: str = None, **fields) -> None:
        """新接口：支持 preset 或直接字段。"""
        if not self._in_bounds(x, y):
            return
        updates = {}
        if preset and preset in self.PRESET_MAP:
            updates.update(self.PRESET_MAP[preset])
        updates.update(fields)
        self._apply_cell_update(x, y, updates)

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
        """已废弃（兼容垫片）。= is_sound_blocking 语义。
        新代码请用 is_passable / is_vision_blocking / is_sound_blocking。"""
        return self.is_sound_blocking(x, y)

    def is_passable(self, x: int, y: int) -> bool:
        """是否可通行（移动碰撞检测）。ADR-1: 布尔是唯一真相。"""
        if not self._in_bounds(x, y):
            return False
        cell = self.map.terrain[y][x]
        if cell.blocks_movement:
            # 门开着 → 可通行（door_open 只在门类型有意义，其他格子保持 False）
            if cell.door_open:
                return True
            return False
        return True

    def is_vision_blocking(self, x: int, y: int) -> bool:
        """是否阻挡视野。ADR-4: 烟雾由 is_smoke 派生，不存两份。"""
        if not self._in_bounds(x, y):
            return True
        cell = self.map.terrain[y][x]
        if cell.is_smoke:
            return True
        if cell.blocks_vision:
            if cell.door_open:
                return False
            return True
        return False

    def is_sound_blocking(self, x: int, y: int) -> bool:
        """是否阻挡声音（听觉/光照传播）。= 实体墙语义（两个布尔都 True）。"""
        if not self._in_bounds(x, y):
            return True
        cell = self.map.terrain[y][x]
        if cell.blocks_movement and cell.blocks_vision:
            if cell.door_open:
                return False
            return True
        return False

    def is_smoke(self, x: int, y: int) -> bool:
        if not self._in_bounds(x, y):
            return False
        return self.map.terrain[y][x].is_smoke
