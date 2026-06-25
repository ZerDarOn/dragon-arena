"""回合时限测试：验证 turn_time_limit_sec 超时后自动 end_turn。

验证 P0：死字段 turn_time_limit_sec 激活。
"""
import asyncio
import time
import pytest

from app.schemas.room import Room, Token, Player
from app.config import RoomConfig
from app.ws.handler import RoomGameState
from app.services.room_snapshot_storage import RoomSnapshotStorage


@pytest.fixture
def gs(temp_db):
    """2 个玩家的 RoomGameState，时限 1 秒（测试用短时限）。"""
    room = Room(id="r1", name="test", config=RoomConfig(
        map_width=10, map_height=10, turn_time_limit_sec=1,
    ))
    room.tokens["t1"] = Token(id="t1", character_name="a", hp=100, max_hp=100, ap=2)
    room.tokens["t2"] = Token(id="t2", character_name="b", hp=100, max_hp=100, ap=2)
    room.turn_order = ["t1", "t2"]
    room.current_actor = "t1"
    room.big_turn = 1
    room.sub_turn = 0

    gs = RoomGameState(room)
    gs.snapshot_storage = RoomSnapshotStorage(db_path=temp_db)
    return gs


@pytest.mark.asyncio
async def test_turn_timer_auto_end_turn(gs):
    """超时后 current_actor 应该从 t1 变成 t2。"""
    assert gs.room.current_actor == "t1"
    # 启动倒计时（1 秒）
    gs.start_turn_timer(callback=lambda: None)  # callback 在测试里不需要广播
    # 等待超时
    await asyncio.sleep(1.5)
    # 超时后应该自动 end_turn
    assert gs.room.current_actor == "t2"


@pytest.mark.asyncio
async def test_turn_timer_cancelled_on_manual_end_turn(gs):
    """手动 end_turn 后，旧倒计时不应再触发。"""
    assert gs.room.current_actor == "t1"
    gs.start_turn_timer(callback=lambda: None)
    # 手动 end_turn
    gs.turn_svc.end_turn()
    gs.cancel_turn_timer()
    assert gs.room.current_actor == "t2"
    # 等待超时时间过去
    await asyncio.sleep(1.5)
    # 不应该再次 end_turn（current_actor 不变）
    assert gs.room.current_actor == "t2"


@pytest.mark.asyncio
async def test_turn_deadline_exposed(gs):
    """turn_deadline 应该暴露给前端渲染倒计时。"""
    gs.start_turn_timer(callback=lambda: None)
    assert gs.turn_deadline is not None
    # deadline 是未来时间戳
    assert gs.turn_deadline > time.time()
    gs.cancel_turn_timer()
