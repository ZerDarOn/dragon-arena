from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from app.config import RoomConfig
from app.schemas.map import GameMap


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
    actor_id: Optional[str] = None  # 关联 Actor 库模板
    character_name: str = ""
    position: Optional[dict] = None  # {x, y}
    facing: int = 0  # 0=N, clockwise, 0-7 (8 directions)
    hp: int = 100
    max_hp: int = 100
    armor: int = 5
    ap: int = 2
    max_ap: int = 2
    gold: int = 0
    score: int = 0
    vision_range: int = 6
    listen_radius: int = 6       # 被动觉察范围（听到/感知未视敌人）
    passive_perception: int = 10 # 被动觉察值（对抗 stealth）
    darkvision: bool = False     # 黑暗视觉：黑暗格仍可见
    stealth: int = 0             # 隐匿值；>0 且在 listen_radius 内需对抗 passive_perception
    states: List[StateTag] = Field(default_factory=list)
    equipment_slots: List[Optional[str]] = Field(default_factory=lambda: [None] * 6)
    skill_slots: List[Optional[str]] = Field(default_factory=lambda: [None, None])
    backpack: List[str] = Field(default_factory=list)
    item_charges: Dict[str, int] = Field(default_factory=dict)  # 道具名 -> 剩余次数
    is_dead: bool = False
    is_hidden: bool = False
    size: int = 1  # 占格大小 1-4
    avatar_url: Optional[str] = None  # 头像 URL（base64 或外部链接）


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
    game_map: Optional[GameMap] = None  # populated on first WS connection
    current_actor: Optional[str] = None
    turn_order: List[str] = Field(default_factory=list)
    big_turn: int = 0
    sub_turn: int = 0
