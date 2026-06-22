"""SQLite-backed storage for users and character sheets.

Design choice: synchronous sqlite3 (not aiosqlite) for simplicity.
Auth operations are rare (login/create user) and each takes ~100ms (bcrypt),
so async would not meaningfully improve throughput. SQLite with check_same_thread=False
is safe for FastAPI's threadpool.
"""
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List

from app.schemas.auth import User, CharacterSheet

_LOCK = threading.Lock()


class UserStorage:
    """Thread-safe SQLite user/character storage."""

    def __init__(self, db_path: str = "backend/data/users.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn, _LOCK:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                nickname TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                last_login_at INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS character_sheets (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                name TEXT NOT NULL,
                gender TEXT DEFAULT '',
                profession TEXT DEFAULT '',
                talent TEXT DEFAULT '',
                hp_base INTEGER DEFAULT 100,
                armor_base INTEGER DEFAULT 5,
                ap_base INTEGER DEFAULT 2,
                gold INTEGER DEFAULT 0,
                backpack TEXT DEFAULT '[]',
                equipment_slots TEXT DEFAULT '[null,null,null,null,null,null]',
                skill_slots TEXT DEFAULT '[null,null]',
                secret_backups TEXT DEFAULT '[]',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_char_owner ON character_sheets(owner_id);
            """)

    # ---- Users ----

    def create_user(self, nickname: str, password_hash: str, is_admin: bool = False) -> User:
        uid = str(uuid.uuid4())
        now = int(time.time() * 1000)
        user = User(
            id=uid, nickname=nickname, password_hash=password_hash,
            is_admin=is_admin, created_at=now, last_login_at=0,
        )
        with self._conn() as conn, _LOCK:
            conn.execute(
                "INSERT INTO users (id, nickname, password_hash, is_admin, created_at, last_login_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user.id, user.nickname, user.password_hash,
                 int(user.is_admin), user.created_at, user.last_login_at),
            )
        return user

    def get_user_by_nickname(self, nickname: str) -> Optional[User]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE nickname = ?", (nickname,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def get_user(self, user_id: str) -> Optional[User]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return self._row_to_user(row) if row else None

    def list_users(self) -> List[User]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [self._row_to_user(r) for r in rows]

    def update_last_login(self, user_id: str) -> None:
        now = int(time.time() * 1000)
        with self._conn() as conn, _LOCK:
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?", (now, user_id)
            )

    def delete_user(self, user_id: str) -> bool:
        with self._conn() as conn, _LOCK:
            cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            # cascade delete character sheets
            conn.execute("DELETE FROM character_sheets WHERE owner_id = ?", (user_id,))
            return cur.rowcount > 0

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> User:
        return User(
            id=row["id"], nickname=row["nickname"],
            password_hash=row["password_hash"],
            is_admin=bool(row["is_admin"]),
            created_at=row["created_at"], last_login_at=row["last_login_at"],
        )

    # ---- Character sheets ----

    def create_character(self, sheet: CharacterSheet) -> CharacterSheet:
        with self._conn() as conn, _LOCK:
            conn.execute(
                """INSERT INTO character_sheets
                (id, owner_id, name, gender, profession, talent,
                 hp_base, armor_base, ap_base, gold,
                 backpack, equipment_slots, skill_slots, secret_backups,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sheet.id, sheet.owner_id, sheet.name, sheet.gender,
                 sheet.profession, sheet.talent,
                 sheet.hp_base, sheet.armor_base, sheet.ap_base, sheet.gold,
                 self._dumps(sheet.backpack), self._dumps(sheet.equipment_slots),
                 self._dumps(sheet.skill_slots), self._dumps(sheet.secret_backups),
                 sheet.created_at, sheet.updated_at),
            )
        return sheet

    def get_character(self, sheet_id: str) -> Optional[CharacterSheet]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM character_sheets WHERE id = ?", (sheet_id,)
            ).fetchone()
        return self._row_to_sheet(row) if row else None

    def list_characters_by_owner(self, owner_id: str) -> List[CharacterSheet]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM character_sheets WHERE owner_id = ? ORDER BY updated_at DESC",
                (owner_id,),
            ).fetchall()
        return [self._row_to_sheet(r) for r in rows]

    def update_character(self, sheet: CharacterSheet) -> bool:
        sheet.updated_at = int(time.time() * 1000)
        with self._conn() as conn, _LOCK:
            cur = conn.execute(
                """UPDATE character_sheets SET
                   name=?, gender=?, profession=?, talent=?,
                   hp_base=?, armor_base=?, ap_base=?, gold=?,
                   backpack=?, equipment_slots=?, skill_slots=?, secret_backups=?,
                   updated_at=?
                   WHERE id=? AND owner_id=?""",
                (sheet.name, sheet.gender, sheet.profession, sheet.talent,
                 sheet.hp_base, sheet.armor_base, sheet.ap_base, sheet.gold,
                 self._dumps(sheet.backpack), self._dumps(sheet.equipment_slots),
                 self._dumps(sheet.skill_slots), self._dumps(sheet.secret_backups),
                 sheet.updated_at, sheet.id, sheet.owner_id),
            )
            return cur.rowcount > 0

    def delete_character(self, sheet_id: str, owner_id: str) -> bool:
        with self._conn() as conn, _LOCK:
            cur = conn.execute(
                "DELETE FROM character_sheets WHERE id=? AND owner_id=?",
                (sheet_id, owner_id),
            )
            return cur.rowcount > 0

    @staticmethod
    def _row_to_sheet(row: sqlite3.Row) -> CharacterSheet:
        import json
        return CharacterSheet(
            id=row["id"], owner_id=row["owner_id"], name=row["name"],
            gender=row["gender"], profession=row["profession"], talent=row["talent"],
            hp_base=row["hp_base"], armor_base=row["armor_base"],
            ap_base=row["ap_base"], gold=row["gold"],
            backpack=json.loads(row["backpack"]),
            equipment_slots=json.loads(row["equipment_slots"]),
            skill_slots=json.loads(row["skill_slots"]),
            secret_backups=json.loads(row["secret_backups"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _dumps(v) -> str:
        import json
        return json.dumps(v)
