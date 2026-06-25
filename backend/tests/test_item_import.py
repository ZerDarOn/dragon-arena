"""道具批量导入：upsert（按 name）/ replace。"""
from app.services.user_storage import UserStorage
from app.schemas.item import ItemCreate


def test_import_items_upsert(tmp_path):
    st = UserStorage(db_path=str(tmp_path / "u.db"))
    st.create_item(ItemCreate(name="剑", category="weapon", price=40))
    res = st.import_items([
        {"name": "剑", "category": "weapon", "price": 60, "effect_text": "改"},  # 更新
        {"name": "盾", "category": "armor", "price": 30},                        # 新增
        {"name": "", "category": "misc"},                                        # 空名跳过
    ])
    assert res["added"] == 1 and res["updated"] == 1
    items = {i["name"]: i for i in st.list_items()}
    assert items["剑"]["price"] == 60 and items["剑"]["effect_text"] == "改"
    assert "盾" in items


def test_import_items_replace(tmp_path):
    st = UserStorage(db_path=str(tmp_path / "u.db"))
    st.create_item(ItemCreate(name="旧", category="misc", price=1))
    st.import_items([{"name": "新", "category": "misc"}], mode="replace")
    assert {i["name"] for i in st.list_items()} == {"新"}
