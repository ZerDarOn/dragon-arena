"""积分排名测试：存活积分累加 + 淘汰顺序 + 最终排名结算。

验证 P0 核心赛制：
- 大回合结束时存活 token 获得 score_survive_per_turn 分
- 玩家死亡时按死亡顺序记录到 elimination_order
- 游戏结束时按淘汰顺序反向套 ranking_table_8p
"""
import pytest

from app.schemas.room import Room, Token, Player
from app.config import RoomConfig
from app.services.turn_service import TurnService


@pytest.fixture
def room():
    """3 个玩家的房间。"""
    r = Room(id="r1", name="test", config=RoomConfig(
        map_width=10, map_height=10,
        score_survive_per_turn=2, score_kill=30,
        ranking_table_8p=[40, 28, 20],
    ))
    r.tokens["t1"] = Token(id="t1", character_name="a", hp=100, max_hp=100, ap=2)
    r.tokens["t2"] = Token(id="t2", character_name="b", hp=100, max_hp=100, ap=2)
    r.tokens["t3"] = Token(id="t3", character_name="c", hp=100, max_hp=100, ap=2)
    r.turn_order = ["t1", "t2", "t3"]
    r.current_actor = "t1"
    r.big_turn = 1
    r.sub_turn = 0
    return r


def test_survive_score_accumulates_on_big_turn(room):
    """大回合（所有人各行动一次）结束时，存活 token 各 +2。"""
    svc = TurnService(room)
    # 走完一轮：t1→t2→t3→回到 t1，触发大回合结算
    svc.end_turn()  # t1 → t2
    svc.end_turn()  # t2 → t3
    svc.end_turn()  # t3 → t1（触发 big_turn+1）
    # 3 人都存活，各 +2
    assert room.tokens["t1"].score == 2
    assert room.tokens["t2"].score == 2
    assert room.tokens["t3"].score == 2


def test_dead_token_gets_no_survive_score(room):
    """死亡的 token 不获得存活积分。"""
    svc = TurnService(room)
    room.tokens["t3"].is_dead = True
    room.turn_order = ["t1", "t2"]  # 死的不在行动序列里
    svc.end_turn()
    svc.end_turn()
    # 触发大回合
    assert room.tokens["t1"].score == 2
    assert room.tokens["t2"].score == 2
    assert room.tokens["t3"].score == 0  # 死了不给分


def test_elimination_order_recorded_on_death(room):
    """玩家死亡时记录淘汰顺序。"""
    svc = TurnService(room)
    # t3 先死
    svc.record_elimination("t3")
    assert room.elimination_order == ["t3"]
    # t1 后死
    svc.record_elimination("t1")
    assert room.elimination_order == ["t3", "t1"]


def test_final_ranking_by_elimination_order(room):
    """最终排名：最后存活者第1名，先死者垫底，套 ranking_table。"""
    svc = TurnService(room)
    # 淘汰顺序：t3（第3名）→ t1（第2名）→ t2 冠军
    svc.record_elimination("t3")
    svc.record_elimination("t1")
    # t2 是冠军（最后存活）
    ranking = svc.compute_final_ranking()
    # ranking_table_8p = [40, 28, 20]
    # t2（冠军）= 40, t1（亚军）= 28, t3（季军）= 20
    assert ranking["t2"] == 40
    assert ranking["t1"] == 28
    assert ranking["t3"] == 20


def test_final_ranking_with_survive_bonus(room):
    """最终排名 = 排名奖励 + 存活积分 + 击杀积分。"""
    svc = TurnService(room)
    # t1 击杀 t3 和 t2，得 60 击杀分
    room.tokens["t1"].score = 60
    # t2 存活 5 回合得 10 分 + 击杀 t1 得 30 分
    room.tokens["t2"].score = 40
    # t3 死了，0 分
    svc.record_elimination("t3")
    svc.record_elimination("t1")
    ranking = svc.compute_final_ranking()
    # t2 冠军 = 40（排名奖励）+ 40（已有积分）= 80
    # t1 亚军 = 28 + 60 = 88  ← 总分最高
    # t3 季军 = 20 + 0 = 20
    # 排名奖励只是基础，最终总分决定名次
    assert ranking["t1"] == 88
    assert ranking["t2"] == 80
    assert ranking["t3"] == 20
