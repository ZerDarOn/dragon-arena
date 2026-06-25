"""内容库（事件/陷阱/怪物/奇遇/NPC）— 规则书 5 个文本库的结构化条目。

跟 ADR-5 / 项目哲学一致：这里只存"这是什么 + 触发/条件 + 效果文字"，系统不解析效果，
团主读 effect_text 手动判定。fields 保留原始表格的全部列，前端可展开看完整信息。
"""
from pydantic import BaseModel
from typing import Dict


class LibraryEntry(BaseModel):
    id: str
    category: str           # event | trap | monster | adventure | npc
    name: str
    tier: str = ""          # 等级 / 稀有度 / 类型（视库而定）
    effect_text: str = ""   # 主效果/描述列（团主参考，系统不解析）
    note: str = ""          # 备注
    fields: Dict[str, str] = {}   # 原始表格全部列，保真展示用
