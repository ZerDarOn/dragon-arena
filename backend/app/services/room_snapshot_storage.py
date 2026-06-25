"""SQLite-backed snapshots for Room/Token/turn 状态。

设计：和 UserStorage 同一 DB 文件（沿用 DRAGON_ARENA_DB_PATH 约定），
同一种 sqlite3 + check_same_thread=False + 模块级 threading.Lock 模式。
每次改写状态的动作后调 save()，进程重启后调 load() 恢复。

不做增量同步——每动作全量快照够用且简单，符合 Phase 1 交底。
"""
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

_LOCK = threading.Lock()


class RoomSnapshotStorage:
    """Room 状态快照存储（thread-safe）。"""

    def __init__(self, db_path: str = "backend/data/users.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn, _LOCK:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS room_snapshots (
                room_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL
            );
            """)

    def save(self, room_id: str, state_json: str) -> None:
        """UPSERT：保存或覆盖某 room 的完整状态快照。"""
        now = int(time.time() * 1000)
        with self._conn() as conn, _LOCK:
            conn.execute(
                """INSERT INTO room_snapshots (room_id, state_json, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(room_id) DO UPDATE SET
                       state_json = excluded.state_json,
                       updated_at = excluded.updated_at""",
                (room_id, state_json, now),
            )

    def load(self, room_id: str) -> Optional[str]:
        """读取快照，返回 state_json 字符串；不存在返回 None。"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT state_json FROM room_snapshots WHERE room_id = ?", (room_id,)
            ).fetchone()
        return row[0] if row else None

    def delete(self, room_id: str) -> bool:
        """删除快照（房间结束时清理）。"""
        with self._conn() as conn, _LOCK:
            cur = conn.execute(
                "DELETE FROM room_snapshots WHERE room_id = ?", (room_id,)
            )
            return cur.rowcount > 0
