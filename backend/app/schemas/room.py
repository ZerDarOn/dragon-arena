from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from app.config import RoomConfig
from app.schemas.map import GameMap


class StateTag(BaseModel):
    """状态标签 — Phase 3 升级为 FVTT 风格的自描述效果对象。

    数据驱动设计（替代硬编码 if-elif）：
    - mode: add/multiply/override/mark。None = 纯标记（如隐身，由业务逻辑检查）
    - target_field: 作用于 token 的哪个属性（如 "armor"），配合 mode 使用
    - value: 效果值（add 时为增量，override 时为目标值，multiply 时为系数）
    - dot_damage: 每回合周期伤害（点燃/中毒/流血）
    - original_value: 应用前记录的原值，过期恢复用
    - source: 效果来源（技能名/道具名/毒圈），用于追溯
    """
    id: str
    name: str
    description: str
    ttl: int
    intensity: Optional[int] = None
    # Phase 3: 数据驱动效果字段
    mode: Optional[str] = None  # add | multiply | override | mark | None
    target_field: Optional[str] = None  # "armor" / "hp" / "ap" 等
    value: Optional[float] = None
    dot_damage: int = 0
    original_value: Optional[float] = None
    source: Optional[str] = None


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
    is_shop: bool = False          # 是否是商店型 NPC
    shop_items: List[str] = Field(default_factory=list)  # 货架上的道具名（对应 Item.name）


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
    # Phase 2: 吃鸡排名——按淘汰顺序记录（先死者垫底）
    elimination_order: List[str] = Field(default_factory=list)
    # 底图（场景背景）——DM 上传后广播给全员
    bg_image: Optional[str] = None          # dataURL
    bg_opacity: float = 0.5
    bg_offset_x: float = 0.0  # 格数，可负
    bg_offset_y: float = 0.0
    bg_scale_x: float = 1.0   # 1=撑满地图
    bg_scale_y: float = 1.0
