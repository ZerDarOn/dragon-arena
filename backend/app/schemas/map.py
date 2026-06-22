from pydantic import BaseModel
from typing import List, Dict, Optional


class TerrainCell(BaseModel):
    x: int
    y: int
    type: str = "flat"  # flat/wall/grass/water/high
    height: int = 0
    smoke_ttl: Optional[int] = None
    is_smoke: bool = False


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
