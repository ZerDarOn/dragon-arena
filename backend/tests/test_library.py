"""内容库：seed 加载 + 分类过滤 + 导入（upsert/replace/自动 id）。"""
from app.services.library_service import LibraryService


def _seed_only(tmp_path):
    """runtime 指向空临时文件 → 只读 seed，导入写入临时文件，不污染真实运行时数据。"""
    return LibraryService(runtime_path=str(tmp_path / "library.json"))


def test_library_seed_loads_all_categories(tmp_path):
    svc = _seed_only(tmp_path)
    entries = svc.list()
    assert len(entries) > 150, "seed 应包含 5 个库共 200 左右条目"
    assert {e.category for e in entries} >= {"event", "trap", "monster", "adventure", "npc"}


def test_library_category_filter(tmp_path):
    svc = _seed_only(tmp_path)
    mons = svc.list("monster")
    assert mons and all(e.category == "monster" for e in mons)
    first = next(e for e in mons if e.name == "野狗")
    assert first.fields.get("生命") == "15"
    assert first.tier == "E"


def test_import_upsert_adds_and_updates(tmp_path):
    svc = _seed_only(tmp_path)
    before = len(svc.list())
    existing = svc.list("monster")[0]
    res = svc.import_entries([
        {"id": "monster_test_new", "category": "monster", "name": "测试史莱姆", "tier": "E", "effect_text": "分裂"},
        {"id": existing.id, "category": "monster", "name": existing.name + "（改）", "effect_text": "改了"},
    ], mode="upsert")
    assert res["added"] == 1 and res["updated"] == 1
    assert len(svc.list()) == before + 1
    # 持久化后重新加载应保留
    svc2 = LibraryService(runtime_path=svc.runtime_path)
    assert any(e.id == "monster_test_new" for e in svc2.list())
    assert next(e for e in svc2.list() if e.id == existing.id).name.endswith("（改）")


def test_import_replace(tmp_path):
    svc = _seed_only(tmp_path)
    res = svc.import_entries([{"category": "event", "name": "唯一事件", "effect_text": "x"}], mode="replace")
    assert res["mode"] == "replace" and res["total"] == 1
    assert len(svc.list()) == 1


def test_import_auto_generates_id(tmp_path):
    svc = _seed_only(tmp_path)
    svc.import_entries([{"category": "trap", "name": "无 id 陷阱"}], mode="replace")
    only = svc.list()[0]
    assert only.id and only.id.startswith("trap_"), "缺 id 应自动生成 category 前缀的 id"
