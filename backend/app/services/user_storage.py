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
            # 兼容旧库：补充新列（IF NOT EXISTS 等价写法——捕获重复列错误）
            for col, ddl in [
                ("darkvision", "INTEGER NOT NULL DEFAULT 0"),
                ("vision_range", "INTEGER NOT NULL DEFAULT 6"),
                ("listen_radius", "INTEGER NOT NULL DEFAULT 6"),
                ("passive_perception", "INTEGER NOT NULL DEFAULT 10"),
                ("stealth", "INTEGER NOT NULL DEFAULT 0"),
                ("avatar_url", "TEXT"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE character_sheets ADD COLUMN {col} {ddl}")
                except Exception:
                    pass  # 列已存在

            # Actor 库表（角色卡模板）
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS actors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'npc',
                avatar_url TEXT,
                hp INTEGER NOT NULL DEFAULT 100,
                max_hp INTEGER NOT NULL DEFAULT 100,
                armor INTEGER NOT NULL DEFAULT 5,
                ap INTEGER NOT NULL DEFAULT 2,
                max_ap INTEGER NOT NULL DEFAULT 2,
                vision_range INTEGER NOT NULL DEFAULT 8,
                darkvision INTEGER NOT NULL DEFAULT 0,
                listen_radius INTEGER NOT NULL DEFAULT 6,
                passive_perception INTEGER NOT NULL DEFAULT 10,
                stealth INTEGER NOT NULL DEFAULT 0,
                equipment_slots TEXT NOT NULL DEFAULT '[null,null,null,null,null,null]',
                skill_slots TEXT NOT NULL DEFAULT '[null,null]',
                backpack TEXT NOT NULL DEFAULT '[]',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_actor_type ON actors(type);

            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'misc',
                description TEXT NOT NULL DEFAULT '',
                effect_text TEXT NOT NULL DEFAULT '',
                icon_url TEXT,
                price INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_item_category ON items(category);
            """)
            for col, ddl in [
                ("is_shop", "INTEGER NOT NULL DEFAULT 0"),
                ("shop_items", "TEXT NOT NULL DEFAULT '[]'"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE actors ADD COLUMN {col} {ddl}")
                except Exception:
                    pass  # 列已存在

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
                (id, owner_id, name, avatar_url, gender, profession, talent,
                 hp_base, armor_base, ap_base, gold,
                 backpack, equipment_slots, skill_slots, secret_backups,
                 darkvision, vision_range, listen_radius, passive_perception, stealth,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sheet.id, sheet.owner_id, sheet.name, sheet.avatar_url, sheet.gender,
                 sheet.profession, sheet.talent,
                 sheet.hp_base, sheet.armor_base, sheet.ap_base, sheet.gold,
                 self._dumps(sheet.backpack), self._dumps(sheet.equipment_slots),
                 self._dumps(sheet.skill_slots), self._dumps(sheet.secret_backups),
                 int(sheet.darkvision), sheet.vision_range, sheet.listen_radius,
                 sheet.passive_perception, sheet.stealth,
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

    def list_all_characters(self) -> List[CharacterSheet]:
        """管理员用：列出全部角色卡（含底牌）。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM character_sheets ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_sheet(r) for r in rows]

    def update_character(self, sheet: CharacterSheet) -> bool:
        sheet.updated_at = int(time.time() * 1000)
        with self._conn() as conn, _LOCK:
            cur = conn.execute(
                """UPDATE character_sheets SET
                   name=?, avatar_url=?, gender=?, profession=?, talent=?,
                   hp_base=?, armor_base=?, ap_base=?, gold=?,
                   backpack=?, equipment_slots=?, skill_slots=?, secret_backups=?,
                   darkvision=?, vision_range=?, listen_radius=?,
                   passive_perception=?, stealth=?,
                   updated_at=?
                   WHERE id=? AND owner_id=?""",
                (sheet.name, sheet.avatar_url, sheet.gender, sheet.profession, sheet.talent,
                 sheet.hp_base, sheet.armor_base, sheet.ap_base, sheet.gold,
                 self._dumps(sheet.backpack), self._dumps(sheet.equipment_slots),
                 self._dumps(sheet.skill_slots), self._dumps(sheet.secret_backups),
                 int(sheet.darkvision), sheet.vision_range, sheet.listen_radius,
                 sheet.passive_perception, sheet.stealth,
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
        keys = row.keys()
        return CharacterSheet(
            id=row["id"], owner_id=row["owner_id"], name=row["name"],
            avatar_url=row["avatar_url"] if "avatar_url" in keys else None,
            gender=row["gender"], profession=row["profession"], talent=row["talent"],
            hp_base=row["hp_base"], armor_base=row["armor_base"],
            ap_base=row["ap_base"], gold=row["gold"],
            backpack=json.loads(row["backpack"]),
            equipment_slots=json.loads(row["equipment_slots"]),
            skill_slots=json.loads(row["skill_slots"]),
            secret_backups=json.loads(row["secret_backups"]),
            darkvision=bool(row["darkvision"]) if "darkvision" in keys else False,
            vision_range=row["vision_range"] if "vision_range" in keys else 6,
            listen_radius=row["listen_radius"] if "listen_radius" in keys else 6,
            passive_perception=row["passive_perception"] if "passive_perception" in keys else 10,
            stealth=row["stealth"] if "stealth" in keys else 0,
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _dumps(v) -> str:
        import json
        return json.dumps(v)

    # ---- Actors (角色卡模板库) ----

    def create_actor(self, data) -> dict:
        import uuid, json
        aid = str(uuid.uuid4())[:8]
        now = int(time.time() * 1000)
        d = data.model_dump()
        with self._conn() as conn, _LOCK:
            conn.execute(
                """INSERT INTO actors (id, name, type, avatar_url, hp, max_hp, armor, ap, max_ap,
                   vision_range, darkvision, listen_radius, passive_perception, stealth,
                   equipment_slots, skill_slots, backpack, is_shop, shop_items, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (aid, d["name"], d["type"], d.get("avatar_url"),
                 d["hp"], d["max_hp"], d["armor"], d["ap"], d["max_ap"],
                 d["vision_range"], d["darkvision"], d["listen_radius"],
                 d["passive_perception"], d["stealth"],
                 json.dumps(d.get("equipment_slots") or [None]*6),
                 json.dumps(d.get("skill_slots") or [None, None]),
                 json.dumps(d.get("backpack") or []),
                 int(d.get("is_shop") or False),
                 json.dumps(d.get("shop_items") or []),
                 now, now),
            )
        return self.get_actor(aid)

    def get_actor(self, actor_id: str) -> Optional[dict]:
        import json
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM actors WHERE id = ?", (actor_id,)).fetchone()
        if not row:
            return None
        return self._row_to_actor(row)

    def list_actors(self, type: Optional[str] = None) -> List[dict]:
        with self._conn() as conn:
            if type:
                rows = conn.execute("SELECT * FROM actors WHERE type = ? ORDER BY created_at DESC", (type,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM actors ORDER BY created_at DESC").fetchall()
        return [self._row_to_actor(r) for r in rows]

    def update_actor(self, actor_id: str, data) -> Optional[dict]:
        import json
        actor = self.get_actor(actor_id)
        if not actor:
            return None
        d = data.model_dump(exclude_unset=True)
        now = int(time.time() * 1000)
        sets = []
        vals = []
        for k, v in d.items():
            if k in ("equipment_slots", "skill_slots", "backpack", "shop_items"):
                sets.append(f"{k} = ?")
                vals.append(json.dumps(v))
            elif k == "is_shop":
                sets.append(f"{k} = ?")
                vals.append(int(v))
            else:
                sets.append(f"{k} = ?")
                vals.append(v)
        sets.append("updated_at = ?")
        vals.append(now)
        vals.append(actor_id)
        with self._conn() as conn, _LOCK:
            conn.execute(f"UPDATE actors SET {', '.join(sets)} WHERE id = ?", vals)
        return self.get_actor(actor_id)

    def delete_actor(self, actor_id: str) -> bool:
        with self._conn() as conn, _LOCK:
            cur = conn.execute("DELETE FROM actors WHERE id = ?", (actor_id,))
            return cur.rowcount > 0

    @staticmethod
    def _row_to_actor(row) -> dict:
        import json
        keys = row.keys()
        return {
            "id": row["id"], "name": row["name"], "type": row["type"],
            "avatar_url": row["avatar_url"], "hp": row["hp"], "max_hp": row["max_hp"],
            "armor": row["armor"], "ap": row["ap"], "max_ap": row["max_ap"],
            "vision_range": row["vision_range"], "darkvision": row["darkvision"],
            "listen_radius": row["listen_radius"],
            "passive_perception": row["passive_perception"], "stealth": row["stealth"],
            "equipment_slots": json.loads(row["equipment_slots"]),
            "skill_slots": json.loads(row["skill_slots"]),
            "backpack": json.loads(row["backpack"]),
            "is_shop": bool(row["is_shop"]) if "is_shop" in keys else False,
            "shop_items": json.loads(row["shop_items"]) if "shop_items" in keys and row["shop_items"] else [],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }

    # ---- Items (道具库) ----

    def create_item(self, data) -> dict:
        import uuid, json
        iid = str(uuid.uuid4())[:8]
        now = int(time.time() * 1000)
        d = data.model_dump()
        with self._conn() as conn, _LOCK:
            conn.execute(
                """INSERT INTO items (id, name, category, description, effect_text, icon_url, price,
                   created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)""",
                (iid, d["name"], d["category"], d["description"], d["effect_text"],
                 d.get("icon_url"), d["price"], now, now),
            )
        return self.get_item(iid)

    def get_item(self, item_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        return self._row_to_item(row) if row else None

    def get_item_by_name(self, name: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM items WHERE name = ?", (name,)).fetchone()
        return self._row_to_item(row) if row else None

    def list_items(self, category: Optional[str] = None) -> List[dict]:
        with self._conn() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM items WHERE category = ? ORDER BY created_at DESC", (category,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM items ORDER BY created_at DESC").fetchall()
        return [self._row_to_item(r) for r in rows]

    def update_item(self, item_id: str, data) -> Optional[dict]:
        item = self.get_item(item_id)
        if not item:
            return None
        d = data.model_dump(exclude_unset=True)
        now = int(time.time() * 1000)
        sets = []
        vals = []
        for k, v in d.items():
            sets.append(f"{k} = ?")
            vals.append(v)
        sets.append("updated_at = ?")
        vals.append(now)
        vals.append(item_id)
        with self._conn() as conn, _LOCK:
            conn.execute(f"UPDATE items SET {', '.join(sets)} WHERE id = ?", vals)
        return self.get_item(item_id)

    def delete_item(self, item_id: str) -> bool:
        with self._conn() as conn, _LOCK:
            cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
            return cur.rowcount > 0

    def import_items(self, entries, mode: str = "upsert") -> dict:
        """批量导入道具。以 name 为键 upsert（货架按 name 引用道具）；replace 先清空。
        entries 为 dict 列表（与导出/ItemCreate 同字段，id 由系统管）。"""
        import uuid
        now = int(time.time() * 1000)
        added = updated = 0
        with self._conn() as conn, _LOCK:
            if mode == "replace":
                conn.execute("DELETE FROM items")
            for e in entries:
                name = (e.get("name") or "").strip()
                if not name:
                    continue
                cat = e.get("category", "misc")
                desc = e.get("description", "")
                eff = e.get("effect_text", "")
                icon = e.get("icon_url")
                price = int(e.get("price", 0) or 0)
                row = conn.execute("SELECT id FROM items WHERE name = ?", (name,)).fetchone()
                if row:
                    conn.execute(
                        "UPDATE items SET category=?, description=?, effect_text=?, icon_url=?, price=?, updated_at=? WHERE id=?",
                        (cat, desc, eff, icon, price, now, row["id"]))
                    updated += 1
                else:
                    conn.execute(
                        "INSERT INTO items (id,name,category,description,effect_text,icon_url,price,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        (str(uuid.uuid4())[:8], name, cat, desc, eff, icon, price, now, now))
                    added += 1
        return {"mode": mode, "added": added, "updated": updated}

    @staticmethod
    def _row_to_item(row) -> dict:
        return {
            "id": row["id"], "name": row["name"], "category": row["category"],
            "description": row["description"], "effect_text": row["effect_text"],
            "icon_url": row["icon_url"], "price": row["price"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
        }
