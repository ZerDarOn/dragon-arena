from typing import List, Tuple, Optional, Dict, Any
from pydantic import BaseModel
from app.schemas.room import Room, Token, StateTag
from app.schemas.map import GameMap
from app.services.geometry_service import angle_to_direction
from app.services.map_service import MapService
import random


class MoveResult(BaseModel):
    success: bool
    reason: str = ""
    new_position: Optional[dict] = None
    new_facing: Optional[int] = None
    ap_consumed: int = 0
    triggered_entities: List[str] = []


class TokenService:
    def __init__(self, room: Room, game_map: GameMap):
        self.room = room
        self.map = game_map
        self.map_svc = MapService(game_map)
        self.cfg = room.config

    def place_token(self, token_id: str, x: int, y: int,
                    character: Optional[dict] = None) -> bool:
        """Place token at (x,y). If character dict provided, apply its snapshot."""
        for t in self.room.tokens.values():
            if t.position == {"x": x, "y": y} and not t.is_dead:
                return False
        if token_id not in self.room.tokens:
            self.room.tokens[token_id] = Token(id=token_id)
        tok = self.room.tokens[token_id]
        tok.position = {"x": x, "y": y}
        # Apply character sheet snapshot if provided
        if character:
            if character.get("name"):
                tok.character_name = character["name"]
            if character.get("avatar_url"):
                tok.avatar_url = character["avatar_url"]
            tok.hp = character.get("hp_base", self.cfg.start_hp)
            tok.max_hp = tok.hp
            tok.armor = character.get("armor_base", self.cfg.start_armor)
            tok.ap = character.get("ap_base", self.cfg.start_ap)
            tok.max_ap = tok.ap
            tok.gold = character.get("gold", 0)
            tok.vision_range = character.get("vision_range", self.cfg.vision_range)
            tok.listen_radius = character.get("listen_radius", 6)
            tok.passive_perception = character.get("passive_perception", 10)
            tok.darkvision = character.get("darkvision", False)
            tok.stealth = character.get("stealth", 0)
            tok.equipment_slots = character.get("equipment_slots", [None] * 6)
            tok.skill_slots = character.get("skill_slots", [None, None])
            tok.backpack = list(character.get("backpack", []))
            # owner_id tracks which user controls this token
            tok.owner_id = character.get("owner_id")
        return True

    def move_along_path(self, token_id: str, path: List[Tuple[int, int]],
                        free_mode: bool = False) -> MoveResult:
        token = self.room.tokens.get(token_id)
        if not token or not token.position:
            return MoveResult(success=False, reason="token has no position")
        if token.is_dead:
            return MoveResult(success=False, reason="token is dead")

        original = (token.position["x"], token.position["y"])
        triggered = []
        ap_needed = 0
        cur = original

        for step in path:
            dx = abs(step[0] - cur[0])
            dy = abs(step[1] - cur[1])
            if max(dx, dy) != 1:
                return MoveResult(success=False, reason=f"non-adjacent step: {cur}->{step}")
            if self.map_svc.is_wall(step[0], step[1]):
                return MoveResult(success=False, reason=f"wall at {step}")
            for other_id, other in self.room.tokens.items():
                if other_id == token_id or other.is_dead:
                    continue
                if other.position == {"x": step[0], "y": step[1]}:
                    return MoveResult(success=False, reason=f"occupied by {other_id}")
            ap_needed += self.cfg.move_ap_cost
            cur = step

        if not free_mode and token.ap < ap_needed:
            return MoveResult(success=False, reason=f"insufficient AP: need {ap_needed}, have {token.ap}")

        if not free_mode:
            token.ap -= ap_needed
        if path:
            last = path[-1]
            token.position = {"x": last[0], "y": last[1]}
            if len(path) >= 2:
                fx = path[-1][0] - path[-2][0]
                fy = path[-1][1] - path[-2][1]
            else:
                fx = path[0][0] - original[0]
                fy = path[0][1] - original[1]
            token.facing = angle_to_direction(fx, fy)

        return MoveResult(
            success=True,
            new_position=token.position,
            new_facing=token.facing,
            ap_consumed=ap_needed,
            triggered_entities=triggered,
        )

    def modify_value(self, token_id: str, field: str, delta: int) -> None:
        token = self.room.tokens.get(token_id)
        if not token or not hasattr(token, field):
            return
        new_val = getattr(token, field) + delta
        if field == "hp":
            new_val = max(0, min(new_val, token.max_hp))
            if new_val == 0:
                token.is_dead = True
        setattr(token, field, new_val)

    def add_state(self, token_id: str, state_id: str, name: str, description: str,
                  ttl: int, intensity: Optional[int] = None) -> None:
        token = self.room.tokens.get(token_id)
        if not token:
            return
        token.states.append(StateTag(
            id=state_id, name=name, description=description,
            ttl=ttl, intensity=intensity,
        ))

    def remove_state(self, token_id: str, state_id: str) -> None:
        token = self.room.tokens.get(token_id)
        if not token:
            return
        token.states = [s for s in token.states if s.id != state_id]

    # ------------------------------------------------------------------
    # 随机落子：DM 一键给所有无位置的玩家 token 分配坐标
    # ------------------------------------------------------------------
    def _occupied_cells(self) -> set:
        """已占用的格子集合（非死亡 token）"""
        return {(t.position["x"], t.position["y"])
                for t in self.room.tokens.values()
                if t.position and not t.is_dead}

    def _walkable_cells(self, area: Optional[Dict[str, int]] = None) -> List[Tuple[int, int]]:
        """返回可通行格列表（非墙、非占用）"""
        occupied = self._occupied_cells()
        cells = []
        if area:
            x1, y1 = area.get("x1", 0), area.get("y1", 0)
            x2, y2 = area.get("x2", self.cfg.map_width), area.get("y2", self.cfg.map_height)
        else:
            x1, y1 = 0, 0
            x2, y2 = self.cfg.map_width, self.cfg.map_height
        for x in range(max(0, x1), min(self.cfg.map_width, x2)):
            for y in range(max(0, y1), min(self.cfg.map_height, y2)):
                if self.map_svc.is_wall(x, y):
                    continue
                if (x, y) in occupied:
                    continue
                cells.append((x, y))
        return cells

    def _edge_cells(self) -> List[Tuple[int, int]]:
        """地图边缘格（外圈 2 格），用于吃鸡式开局分布"""
        occupied = self._occupied_cells()
        cells = []
        w, h = self.cfg.map_width, self.cfg.map_height
        for x in range(w):
            for y in range(h):
                # 外圈 2 格
                if min(x, y, w - 1 - x, h - 1 - y) >= 2:
                    continue
                if self.map_svc.is_wall(x, y):
                    continue
                if (x, y) in occupied:
                    continue
                cells.append((x, y))
        return cells

    def random_placement(self, mode: str = "all",
                         area: Optional[Dict[str, int]] = None) -> List[str]:
        """给所有 position 为空的 token 随机分配坐标。

        mode:
          - all:  全图随机
          - area: 指定矩形区域随机（需提供 area={x1,y1,x2,y2}）
          - edge: 边缘分布（吃鸡开局）
        返回已放置的 token_id 列表。
        """
        # 候选 token：有 owner、无 position、非死亡
        candidates = [t for t in self.room.tokens.values()
                      if t.owner_id and not t.position and not t.is_dead]
        if not candidates:
            return []

        if mode == "edge":
            pool = self._edge_cells()
        elif mode == "area":
            pool = self._walkable_cells(area)
        else:
            pool = self._walkable_cells()

        random.shuffle(pool)
        placed = []
        for tok in candidates:
            if not pool:
                break
            x, y = pool.pop()
            tok.position = {"x": x, "y": y}
            placed.append(tok.id)
        return placed
