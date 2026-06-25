"""抽取表（RollTable）— 通用加权随机抽取原语。

规则书里大量"随机抽一个"（随机事件/空投/掉落/搜刮/奇遇）现在可以机制化：
建一张表 → 抽 → 得到一条结果，团主照常念效果手动判定（不违反"不自动结算"哲学）。

两种模式：
- source_category 设了（event/trap/monster/adventure/npc）→ 从内容库该分类随机抽，零录入。
- 否则 → 从 entries 加权随机抽（团主自定义条目）。
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class RollEntry(BaseModel):
    weight: int = 1
    text: str
    ref: str = ""   # 可选：关联 library/item id（暂仅展示）


class RollTable(BaseModel):
    id: str
    name: str
    description: str = ""
    source_category: str = ""   # 设置则从内容库该分类抽，忽略 entries
    entries: List[RollEntry] = []


class DrawResult(BaseModel):
    table_id: str
    table_name: str
    text: str
    ref: str = ""
    entry: Optional[Dict[str, Any]] = None   # 来自内容库时附带完整条目
