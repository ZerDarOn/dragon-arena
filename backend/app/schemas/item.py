"""Item (道具/装备库) Pydantic schemas.

跟 ADR-5 一致：这里只存"这个道具是什么"的描述性数据（名字/分类/价格/效果文字），
不存任何可执行的效果逻辑——具体效果怎么生效，还是团主看 effect_text 手动判定。
"""
from pydantic import BaseModel, Field
from typing import Optional


class ItemBase(BaseModel):
    name: str
    category: str = "misc"  # weapon | armor | consumable | skill | misc
    description: str = ""
    effect_text: str = ""  # 团主参考用的效果描述，系统不解析
    icon_url: Optional[str] = None
    price: int = 0  # 0 = 不可购买（只能战场获得/团主发放）


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    effect_text: Optional[str] = None
    icon_url: Optional[str] = None
    price: Optional[int] = None


class ItemOut(ItemBase):
    id: str
    created_at: int
    updated_at: int
