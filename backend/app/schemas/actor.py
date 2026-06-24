"""Actor (character card template) Pydantic schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List
import time


class ActorBase(BaseModel):
    name: str
    type: str = "npc"  # player, npc, monster
    avatar_url: Optional[str] = None
    hp: int = 100
    max_hp: int = 100
    armor: int = 5
    ap: int = 2
    max_ap: int = 2
    vision_range: int = 8
    darkvision: int = 0
    listen_radius: int = 6
    passive_perception: int = 10
    stealth: int = 0
    equipment_slots: List[Optional[str]] = Field(default_factory=lambda: [None] * 6)
    skill_slots: List[Optional[str]] = Field(default_factory=lambda: [None, None])
    backpack: List[str] = Field(default_factory=list)


class ActorCreate(ActorBase):
    pass


class ActorUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    avatar_url: Optional[str] = None
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    armor: Optional[int] = None
    ap: Optional[int] = None
    max_ap: Optional[int] = None
    vision_range: Optional[int] = None
    darkvision: Optional[int] = None
    listen_radius: Optional[int] = None
    passive_perception: Optional[int] = None
    stealth: Optional[int] = None
    equipment_slots: Optional[List[Optional[str]]] = None
    skill_slots: Optional[List[Optional[str]]] = None
    backpack: Optional[List[str]] = None


class ActorOut(ActorBase):
    id: str
    created_at: int
    updated_at: int
