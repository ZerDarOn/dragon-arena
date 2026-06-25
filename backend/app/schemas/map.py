from pydantic import BaseModel
from typing import List, Dict, Optional


class TerrainCell(BaseModel):
    x: int
    y: int
    type: str = "flat"  # flat/wall/grass/water/high
    height: int = 0
    smoke_ttl: Optional[int] = None
    is_smoke: bool = False
    is_dark: bool = False           # 环境黑暗格（洞穴/夜晚），无光源且无黑暗视觉则不可见
    darkness_strength: float = 0.7  # 暗度 0.0-1.0（DM 可调，默认 0.7）
    light_radius: int = 0           # 光源照亮半径（0=非光源；火把/篝火/法术光>0）


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
