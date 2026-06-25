"""战争迷雾视野系统（后端权威）。

可见性判定顺序：
1. 扇形过滤（朝向 ±45° 全视野，侧 ±90° 看 3 格，背后盲区）
2. 视线阻挡（墙/烟雾阻挡 Bresenham 直线）
3. 光源扩散（任意光源点亮的格子视为明亮，跳过黑暗判定）
4. 黑暗过滤（is_dark 且无光且无 darkvision → 不可见）

被动觉察（listen_radius）：隐匿敌人在 listen_radius 内，
若其 stealth < 玩家 passive_perception → 在 detected_tokens 中标记方位。
"""
from typing import Set, List, Tuple, Dict
from app.schemas.room import Room, Token
from app.schemas.map import GameMap
from app.services.geometry_service import (
    chebyshev_distance, is_in_sector, bresenham_line, angle_to_direction,
)
from app.services.map_service import MapService


class VisionService:
    def __init__(self, room: Room, game_map: GameMap):
        self.room = room
        self._game_map = game_map
        self.cfg = room.config

    @property
    def map(self) -> GameMap:
        """动态读 room.game_map，避免 resize 后引用过期。"""
        return self.room.game_map or self._game_map

    @property
    def map_svc(self) -> MapService:
        """每次创建新 MapService（轻量），确保引用最新地图。"""
        return MapService(self.map)

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def compute_visible_cells(self, token_id: str) -> Set[Tuple[int, int]]:
        """返回该 token 可见的格子集合（含自身）。"""
        token = self.room.tokens.get(token_id)
        if not token or not token.position:
            return set()
        origin = (token.position["x"], token.position["y"])
        vr = token.vision_range

        # 第一步：扇形 + 视线阻挡
        candidates: Set[Tuple[int, int]] = {origin}
        for y in range(self.map.height):
            for x in range(self.map.width):
                target = (x, y)
                if target == origin:
                    continue
                if not is_in_sector(origin, token.facing, target, vr):
                    continue
                if self._is_blocked(origin, target):
                    continue
                candidates.add(target)

        # 第二步：光源扩散——任何光源点亮的格子加入候选
        lit = self._compute_lit_cells(origin, vr)
        candidates |= lit

        # 第三步：黑暗过滤
        if token.darkvision:
            return candidates  # 黑暗视觉无视黑暗
        # 始终保留自身所在格：即使站在暗格里、没光没黑暗视觉，玩家也得看得见自己，
        # 否则会在黑暗中从自己的视野里"消失"（self token 不渲染）。
        return {c for c in candidates if c == origin or not self._is_dark_cell(c)}

    def compute_visible_tokens(self, token_id: str) -> List[str]:
        """完全可见的 token（在可见格子上）。"""
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

    def compute_detected_tokens(self, token_id: str) -> Dict[str, str]:
        """被动觉察：返回 {token_id: 方位名}，只露方位不露坐标。

        规则：对方在 listen_radius 内 + 对方 stealth < 玩家 passive_perception
              + 视线没被墙完全阻挡（允许穿烟雾/黑暗感知声音）
        """
        token = self.room.tokens.get(token_id)
        if not token or not token.position:
            return {}
        origin = (token.position["x"], token.position["y"])
        lr = token.listen_radius
        names = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
        result: Dict[str, str] = {}
        visible_set = self.compute_visible_cells(token_id)
        for other_id, other in self.room.tokens.items():
            if other_id == token_id or other.is_dead or not other.position:
                continue
            if other.is_hidden:
                continue
            pos = (other.position["x"], other.position["y"])
            # 已完全可见的不重复标
            if pos in visible_set:
                continue
            dist = chebyshev_distance(origin, pos)
            if dist > lr:
                continue
            # 隐匿对抗
            if other.stealth > 0 and other.stealth >= token.passive_perception:
                continue  # 隐匿成功，感知不到
            # 墙阻挡（声音不穿墙，但可穿烟雾/黑暗）
            if self._is_wall_blocked(origin, pos):
                continue
            dx, dy = pos[0] - origin[0], pos[1] - origin[1]
            result[other_id] = names[angle_to_direction(dx, dy)]
        return result

    def compute_direction_aware_targets(self, token_id: str) -> dict:
        """遗留接口：保留旧名字供兼容。"""
        return self.compute_detected_tokens(token_id)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _is_blocked(self, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        """视线被墙或烟雾阻挡。"""
        cells = bresenham_line(a, b)
        for (x, y) in cells[1:-1]:
            if self.map_svc.is_wall(x, y):
                return True
            if self.map_svc.is_smoke(x, y):
                return True
        return False

    def _is_wall_blocked(self, a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        """仅墙阻挡（声音穿烟雾/黑暗）。"""
        cells = bresenham_line(a, b)
        for (x, y) in cells[1:-1]:
            if self.map_svc.is_wall(x, y):
                return True
        return False

    def _is_dark_cell(self, pos: Tuple[int, int]) -> bool:
        x, y = pos
        if not self.map_svc._in_bounds(x, y):
            return False
        return self.map.terrain[y][x].is_dark

    def _is_lit(self, pos: Tuple[int, int]) -> bool:
        """该格被任意光源照亮。"""
        x, y = pos
        if not self.map_svc._in_bounds(x, y):
            return False
        # 自身是光源
        if self.map.terrain[y][x].light_radius > 0:
            return True
        # 检查所有光源
        for ly in range(self.map.height):
            for lx in range(self.map.width):
                cell = self.map.terrain[ly][lx]
                if cell.light_radius <= 0:
                    continue
                if chebyshev_distance((lx, ly), pos) <= cell.light_radius:
                    # 光源到该格不被墙挡
                    if not self._is_wall_blocked((lx, ly), pos):
                        return True
        return False

    def _compute_lit_cells(self, origin: Tuple[int, int], vr: int) -> Set[Tuple[int, int]]:
        """收集所有在玩家视野范围内被光源点亮的格子。"""
        lit: Set[Tuple[int, int]] = set()
        for y in range(self.map.height):
            for x in range(self.map.width):
                cell = self.map.terrain[y][x]
                if cell.light_radius <= 0:
                    continue
                # 光源到玩家的距离在视野内才考虑
                src = (x, y)
                if chebyshev_distance(src, origin) > vr + cell.light_radius:
                    continue
                # 点亮光源周围
                for ly in range(max(0, y - cell.light_radius),
                                min(self.map.height, y + cell.light_radius + 1)):
                    for lx in range(max(0, x - cell.light_radius),
                                    min(self.map.width, x + cell.light_radius + 1)):
                        target = (lx, ly)
                        if chebyshev_distance(src, target) > cell.light_radius:
                            continue
                        if not self._is_wall_blocked(src, target):
                            lit.add(target)
        return lit
