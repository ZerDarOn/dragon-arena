"""抽取表：seed 加载 + 两种抽取模式 + CRUD 持久化。"""
from app.services.rolltable_service import RollTableService


def _svc(tmp_path):
    return RollTableService(runtime_path=str(tmp_path / "rolltables.json"))


def test_seed_loads(tmp_path):
    svc = _svc(tmp_path)
    tables = svc.list()
    assert len(tables) >= 3
    assert any(t.source_category == "event" for t in tables)


def test_draw_from_library_category(tmp_path):
    svc = _svc(tmp_path)
    res = svc.draw("rt_random_event")
    assert res and res.entry and res.entry["category"] == "event"
    assert res.text  # 抽到的事件名


def test_draw_weighted_entries(tmp_path):
    svc = _svc(tmp_path)
    res = svc.draw("rt_airdrop")
    assert res and res.text in {
        "随机 D 级装备 ×1", "随机 C 级道具 ×1", "随机 B 级装备 ×1", "金币 50G",
    }


def test_crud_and_persist(tmp_path):
    svc = _svc(tmp_path)
    t = svc.create({"name": "测试表", "entries": [{"weight": 1, "text": "A"}]})
    assert t.id and svc.draw(t.id).text == "A"
    svc.update(t.id, {"name": "改名", "entries": [{"weight": 1, "text": "B"}]})
    assert svc.get(t.id).name == "改名"
    # 持久化往返
    svc2 = RollTableService(runtime_path=svc.path)
    assert svc2.get(t.id).name == "改名"
    assert svc.delete(t.id) is True and svc.get(t.id) is None
