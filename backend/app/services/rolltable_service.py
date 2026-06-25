"""抽取表服务：CRUD + 加权抽取，持久化到运行时文件。

运行时 backend/data/rolltables.json（gitignore）优先，回退到提交的 seed。
抽取在服务端进行（权威），与服务端权威骰子一致。
"""
import json
import os
import random
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.schemas.rolltable import RollTable, DrawResult
from app.services.library_service import library_service

_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "rolltable_seed.json"
_RUNTIME_PATH = os.environ.get("DRAGON_ARENA_ROLLTABLE_PATH", "backend/data/rolltables.json")


class RollTableService:
    def __init__(self, runtime_path: Optional[str] = None):
        self.path = Path(runtime_path or _RUNTIME_PATH)
        self._tables: Dict[str, RollTable] = {}
        self._load()

    def _load(self) -> None:
        src = self.path if self.path.exists() else _SEED_PATH
        if src.exists():
            data = json.loads(src.read_text(encoding="utf-8"))
            self._tables = {t["id"]: RollTable(**t) for t in data}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([t.model_dump() for t in self._tables.values()], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list(self) -> List[RollTable]:
        return list(self._tables.values())

    def get(self, tid: str) -> Optional[RollTable]:
        return self._tables.get(tid)

    def create(self, data: Dict[str, Any]) -> RollTable:
        tid = data.get("id") or f"rt_{uuid.uuid4().hex[:8]}"
        table = RollTable(**{**data, "id": tid})
        self._tables[tid] = table
        self._persist()
        return table

    def update(self, tid: str, data: Dict[str, Any]) -> Optional[RollTable]:
        if tid not in self._tables:
            return None
        table = RollTable(**{**data, "id": tid})
        self._tables[tid] = table
        self._persist()
        return table

    def delete(self, tid: str) -> bool:
        if tid in self._tables:
            del self._tables[tid]
            self._persist()
            return True
        return False

    def draw(self, tid: str) -> Optional[DrawResult]:
        table = self._tables.get(tid)
        if not table:
            return None
        # 模式一：从内容库某分类随机抽
        if table.source_category:
            pool = library_service.list(table.source_category)
            if not pool:
                return DrawResult(table_id=tid, table_name=table.name, text="（内容库该分类为空）")
            e = random.choice(pool)
            return DrawResult(table_id=tid, table_name=table.name, text=e.name, ref=e.id, entry=e.model_dump())
        # 模式二：加权自定义条目
        if not table.entries:
            return DrawResult(table_id=tid, table_name=table.name, text="（空表）")
        weights = [max(1, e.weight) for e in table.entries]
        chosen = random.choices(table.entries, weights=weights, k=1)[0]
        return DrawResult(table_id=tid, table_name=table.name, text=chosen.text, ref=chosen.ref)


# 模块级单例
rolltable_service = RollTableService()
