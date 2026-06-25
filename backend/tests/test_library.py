"""内容库 seed 加载 + 分类过滤。"""
from app.services.library_service import library_service


def test_library_seed_loads_all_categories():
    entries = library_service.list()
    assert len(entries) > 150, "seed 应包含 5 个库共 200 左右条目"
    cats = {e.category for e in entries}
    assert cats >= {"event", "trap", "monster", "adventure", "npc"}


def test_library_category_filter():
    mons = library_service.list("monster")
    assert mons and all(e.category == "monster" for e in mons)
    assert any(e.name == "野狗" for e in mons), "怪物库应解析出第一条「野狗」"
    # 原始列保真：怪物条目应保留生命/护甲等列
    first = next(e for e in mons if e.name == "野狗")
    assert first.fields.get("生命") == "15"
    assert first.tier == "E"
