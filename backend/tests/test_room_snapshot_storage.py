"""RoomSnapshotStorage 测试：room 状态快照的保存与恢复。

验证 A-2 持久化：进程重启后能从快照恢复完整 Room 状态。
"""
import os
import tempfile
import pytest

from app.schemas.room import Room, Token, Player
from app.config import RoomConfig
from app.services.room_snapshot_storage import RoomSnapshotStorage


@pytest.fixture
def snapshot_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    storage = RoomSnapshotStorage(db_path=path)
    yield storage
    try:
        os.unlink(path)
    except OSError:
        pass


def _make_room(room_id: str = "r1") -> Room:
    """构造一个有 token、玩家、配置改动的 Room。"""
    room = Room(id=room_id, name="test", config=RoomConfig(map_width=20, map_height=20))
    room.players["p1"] = Player(id="p1", name="alice", nickname="alice", token_id="t1")
    room.tokens["t1"] = Token(
        id="t1", character_name="hero", hp=80, max_hp=100,
        position={"x": 5, "y": 5}, armor=3, ap=1,
    )
    room.turn_order = ["t1"]
    room.current_actor = "t1"
    room.big_turn = 3
    room.sub_turn = 2
    return room


def test_save_and_load_roundtrip(snapshot_db):
    """保存后立即读取，状态完全一致。"""
    room = _make_room()
    snapshot_db.save(room.id, room.model_dump_json())

    loaded = snapshot_db.load(room.id)
    assert loaded is not None
    restored = Room.model_validate_json(loaded)
    assert restored.id == room.id
    assert restored.name == room.name
    assert restored.config.map_width == 20
    assert restored.tokens["t1"].hp == 80
    assert restored.tokens["t1"].position == {"x": 5, "y": 5}
    assert restored.turn_order == ["t1"]
    assert restored.big_turn == 3
    assert restored.current_actor == "t1"


def test_load_missing_returns_none(snapshot_db):
    """读不存在的快照返回 None。"""
    assert snapshot_db.load("nonexistent") is None


def test_save_overwrites_previous(snapshot_db):
    """重复保存同一 room 覆盖旧快照（UPSERT）。"""
    room = _make_room()
    room.tokens["t1"].hp = 80
    snapshot_db.save(room.id, room.model_dump_json())

    room.tokens["t1"].hp = 50  # 状态改变
    snapshot_db.save(room.id, room.model_dump_json())

    loaded = snapshot_db.load(room.id)
    restored = Room.model_validate_json(loaded)
    assert restored.tokens["t1"].hp == 50  # 是新值，不是旧值


def test_states_persisted(snapshot_db):
    """StateTag 列表能完整往返。"""
    from app.schemas.room import StateTag
    room = _make_room()
    room.tokens["t1"].states.append(StateTag(
        id="s1", name="点燃", description="每回合2伤害", ttl=3, intensity=2,
    ))
    snapshot_db.save(room.id, room.model_dump_json())

    restored = Room.model_validate_json(snapshot_db.load(room.id))
    assert len(restored.tokens["t1"].states) == 1
    assert restored.tokens["t1"].states[0].name == "点燃"
    assert restored.tokens["t1"].states[0].ttl == 3
