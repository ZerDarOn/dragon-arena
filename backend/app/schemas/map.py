from pydantic import BaseModel, model_validator
from typing import List, Dict, Optional


# ─── 迁移映射：旧 type → 新三维字段（§5.1） ───
_LEGACY_MIGRATION = {
    "wall": {"terrain_type": "stone", "blocks_movement": True,
             "blocks_vision": True, "wall_render": "solid"},
    "grass": {"terrain_type": "grass"},
    "water": {"terrain_type": "water"},
    "high": {"terrain_type": "stone"},  # height 字段保留
}


class TerrainCell(BaseModel):
    x: int
    y: int

    # ─── 维度1: 地貌（纯视觉） ───
    terrain_type: str = "flat"
    # flat/grass/dirt/stone/sand/water/lava/ice/wood/glass/poison

    # ─── 维度2: 碰撞（唯一真相，ADR-1） ───
    blocks_movement: bool = False
    blocks_vision: bool = False

    # ─── 渲染标签（不影响碰撞，ADR-1） ───
    wall_render: Optional[str] = None
    # None/solid/door/glass/water_deep/lava
    door_open: bool = False

    # ─── 维度3: 环境 ───
    height: int = 0
    smoke_ttl: Optional[int] = None
    is_smoke: bool = False
    is_dark: bool = False
    darkness_strength: float = 0.7
    light_radius: int = 0

    # ─── 废弃（迁移期保留） ───
    type: Optional[str] = None  # 旧字段，迁移后清空


class GameMap(BaseModel):
    width: int
    height: int
    terrain: List[List[TerrainCell]]
    safe_zone: Dict

    def __init__(self, **data):
        width = data.get("width", 30)
        height = data.get("height", 30)
        if "terrain" not in data:
            data["terrain"] = [
                [TerrainCell(x=x, y=y) for x in range(width)]
                for y in range(height)
            ]
        if "safe_zone" not in data:
            data["safe_zone"] = {
                "center": {"x": width // 2, "y": height // 2},
                "radius": max(width, height) // 2,
            }
        super().__init__(**data)

    @model_validator(mode="after")
    def migrate_legacy_terrain(self):
        """懒加载迁移：旧 type 字段 → 新三维字段（§5.2）。
        覆盖快照恢复路径（老 JSON 只有 type 字段）。"""
        for row in self.terrain:
            for cell in row:
                legacy = cell.type
                if not legacy or legacy == "flat":
                    continue
                updates = _LEGACY_MIGRATION.get(legacy, {})
                for k, v in updates.items():
                    # 规则：不覆盖已被显式设置的值
                    #   blocks_movement/blocks_vision：True 视为已设
                    #   terrain_type：非 "flat" 视为已设
                    #   其他：非 None/空 视为已设
                    cur = getattr(cell, k, None)
                    if k in ("blocks_movement", "blocks_vision"):
                        if cur:
                            continue
                    elif k == "terrain_type":
                        if cur and cur != "flat":
                            continue
                    elif cur:
                        continue
                    setattr(cell, k, v)
                cell.type = None  # 清除旧字段
        return self
