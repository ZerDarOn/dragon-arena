from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from app.config import RoomConfig


class StateTag(BaseModel):
    id: str
    name: str
    description: str
    ttl: int
    intensity: Optional[int] = None


class Token(BaseModel):
    id: str
    type: str = "player"  # player/monster/summon/corpse/drop
    owner_id: Optional[str] = None
    position: Optional[dict] = None  # {x, y}
    facing: int = 0  # 0=N, clockwise
    hp: int = 100
    max_hp: int = 100
    armor: int = 5
    ap: int = 2
    max_ap: int = 2
    gold: int = 0
    score: int = 0
    vision_range: int = 6
    listen_radius: int = 6
    states: List[StateTag] = Field(default_factory=list)
    equipment_slots: List[Optional[str]] = Field(default_factory=lambda: [None] * 6)
    skill_slots: List[Optional[str]] = Field(default_factory=lambda: [None, None])
    backpack: List[str] = Field(default_factory=list)
    is_dead: bool = False
    is_hidden: bool = False


class Player(BaseModel):
    id: str
    name: str
    is_host: bool = False
    is_connected: bool = True
    token_id: Optional[str] = None
    nickname: str = ""
    character_name: str = ""
    gender: str = ""
    profession: str = ""
    talent: str = ""


class Room(BaseModel):
    id: str
    name: str
    config: RoomConfig = RoomConfig()
    players: Dict[str, Player] = Field(default_factory=dict)
    tokens: Dict[str, Token] = Field(default_factory=dict)
    current_actor: Optional[str] = None
    turn_order: List[str] = Field(default_factory=list)
    big_turn: int = 0
    sub_turn: int = 0
