"""内容库服务：可读 + 可导入持久化。

数据来源优先级：运行时文件（含团主/AI 导入的内容，可写）> 提交进仓库的 seed。
seed 由 scripts/import_libraries.py 从规则书文本库一次性生成；导入后写入运行时文件
（backend/data/library.json，已 gitignore，与 users.db 同目录），重启后保留。

格式即规范：导出/导入都是一个 LibraryEntry 数组，round-trip 一致——后期 AI 读 Excel
整理成这个数组就能一键导入。id 可省略（导入时自动生成）。
"""
import json
import os
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.schemas.library import LibraryEntry

_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "library_seed.json"
_RUNTIME_PATH = os.environ.get("DRAGON_ARENA_LIBRARY_PATH", "backend/data/library.json")


class LibraryService:
    def __init__(self, runtime_path: Optional[str] = None, seed_path: Path = _SEED_PATH):
        self.runtime_path = Path(runtime_path or _RUNTIME_PATH)
        self.seed_path = seed_path
        self._entries: List[LibraryEntry] = []
        self._load()

    def _load(self) -> None:
        # 运行时文件优先（含导入内容），否则回退到提交的 seed
        src = self.runtime_path if self.runtime_path.exists() else self.seed_path
        if src.exists():
            data = json.loads(src.read_text(encoding="utf-8"))
            self._entries = [LibraryEntry(**e) for e in data]

    def _persist(self) -> None:
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_path.write_text(
            json.dumps([e.model_dump() for e in self._entries], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list(self, category: Optional[str] = None) -> List[LibraryEntry]:
        if category:
            return [e for e in self._entries if e.category == category]
        return list(self._entries)

    def import_entries(self, entries: List[Dict[str, Any]], mode: str = "upsert") -> Dict[str, Any]:
        """导入条目并持久化。

        mode:
          - upsert（默认）：按 id 合并，已存在则覆盖，不存在则新增
          - replace：整库替换为传入内容
        条目缺 id 时自动生成 `{category}_{8位}`。返回计数供前端提示。
        """
        normalized: List[Dict[str, Any]] = []
        for e in entries:
            e = dict(e)
            if not e.get("id"):
                e["id"] = f"{e.get('category', 'x')}_{uuid.uuid4().hex[:8]}"
            normalized.append(e)
        parsed = [LibraryEntry(**e) for e in normalized]  # 校验；非法直接抛 → 400

        if mode == "replace":
            removed = len(self._entries)
            self._entries = parsed
            self._persist()
            return {"mode": "replace", "total": len(parsed), "removed": removed}

        by_id = {e.id: e for e in self._entries}
        added = updated = 0
        for e in parsed:
            if e.id in by_id:
                updated += 1
            else:
                added += 1
            by_id[e.id] = e
        self._entries = list(by_id.values())
        self._persist()
        return {"mode": "upsert", "added": added, "updated": updated, "total": len(self._entries)}


# 模块级单例：进程内加载一次
library_service = LibraryService()
