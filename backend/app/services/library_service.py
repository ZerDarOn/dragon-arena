"""内容库服务：启动时把 library_seed.json 载入内存，提供只读查询。

seed 由 scripts/import_libraries.py 从规则书文本库一次性生成并提交进仓库，
运行时不依赖外部源文件。目前是只读参考内容；将来要支持团主在线增删改，
在这里加持久化即可，调用方/前端不用变。
"""
import json
from pathlib import Path
from typing import List, Optional

from app.schemas.library import LibraryEntry

_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "library_seed.json"


class LibraryService:
    def __init__(self, seed_path: Path = _SEED_PATH):
        self._entries: List[LibraryEntry] = []
        if seed_path.exists():
            data = json.loads(seed_path.read_text(encoding="utf-8"))
            self._entries = [LibraryEntry(**e) for e in data]

    def list(self, category: Optional[str] = None) -> List[LibraryEntry]:
        if category:
            return [e for e in self._entries if e.category == category]
        return list(self._entries)


# 模块级单例：seed 是静态参考数据，进程内加载一次即可
library_service = LibraryService()
