from pydantic import BaseModel, Field
from typing import Optional, List
import time


class User(BaseModel):
    """User account. password_hash never serialized to client."""
    id: str
    nickname: str
    password_hash: str = ""  # bcrypt hash, excluded from responses
    is_admin: bool = False
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    last_login_at: int = 0


class UserPublic(BaseModel):
    """User fields safe to expose to clients."""
    id: str
    nickname: str
    is_admin: bool
    created_at: int
    last_login_at: int


class LoginRequest(BaseModel):
    nickname: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: UserPublic


class CreateUserRequest(BaseModel):
    nickname: str
    password: str
    is_admin: bool = False


class CharacterSheet(BaseModel):
    """Player-defined character template. secret_backups visible only to owner/admin."""
    id: str
    owner_id: str
    name: str
    gender: str = ""
    profession: str = ""
    talent: str = ""
    hp_base: int = 100
    armor_base: int = 5
    ap_base: int = 2
    gold: int = 0
    backpack: List[str] = Field(default_factory=list)
    equipment_slots: List[Optional[str]] = Field(default_factory=lambda: [None] * 6)
    skill_slots: List[Optional[str]] = Field(default_factory=lambda: [None, None])
    secret_backups: List[str] = Field(default_factory=list)
    created_at: int = Field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = Field(default_factory=lambda: int(time.time() * 1000))


class CharacterSheetPublic(BaseModel):
    """Character sheet with secret_backups stripped for non-owner viewers."""
    id: str
    owner_id: str
    name: str
    gender: str = ""
    profession: str = ""
    talent: str = ""
    hp_base: int = 100
    armor_base: int = 5
    ap_base: int = 2
    gold: int = 0
    backpack: List[str] = Field(default_factory=list)
    equipment_slots: List[Optional[str]] = Field(default_factory=lambda: [None] * 6)
    skill_slots: List[Optional[str]] = Field(default_factory=lambda: [None, None])
    created_at: int = 0
    updated_at: int = 0


class CreateCharacterRequest(BaseModel):
    name: str
    gender: str = ""
    profession: str = ""
    talent: str = ""
    hp_base: int = 100
    armor_base: int = 5
    ap_base: int = 2
    gold: int = 0
    backpack: List[str] = Field(default_factory=list)
    equipment_slots: List[Optional[str]] = Field(default_factory=lambda: [None] * 6)
    skill_slots: List[Optional[str]] = Field(default_factory=lambda: [None, None])
    secret_backups: List[str] = Field(default_factory=list)


def to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id, nickname=user.nickname, is_admin=user.is_admin,
        created_at=user.created_at, last_login_at=user.last_login_at,
    )


def sheet_to_public(sheet: CharacterSheet) -> CharacterSheetPublic:
    """Strip secret_backups for non-owner/admin viewers."""
    return CharacterSheetPublic(
        id=sheet.id, owner_id=sheet.owner_id, name=sheet.name,
        gender=sheet.gender, profession=sheet.profession, talent=sheet.talent,
        hp_base=sheet.hp_base, armor_base=sheet.armor_base, ap_base=sheet.ap_base,
        gold=sheet.gold, backpack=sheet.backpack,
        equipment_slots=sheet.equipment_slots, skill_slots=sheet.skill_slots,
        created_at=sheet.created_at, updated_at=sheet.updated_at,
    )
