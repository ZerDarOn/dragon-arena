"""Tests for the shop NPC + buy_item flow."""
import pytest


@pytest.fixture
def ws_room(auth_client):
    r = auth_client.post("/rooms", json={"name": "shop-test"})
    return r.json()["id"]


def _setup_shop_and_buyer(ws, item_name="治疗药水", price=10, buyer_gold=50):
    """放一个商店 NPC + 一个买家 token，给买家一些金币。返回 (shop_token_id, buyer_token_id)。"""
    ws.send_json({"type": "place_unit", "payload": {
        "unit_type": "npc", "name": "杂货商", "x": 1, "y": 1,
        "is_shop": True, "shop_items": [item_name],
    }})
    msg = ws.receive_json()
    shop_id = [tid for tid, t in msg["payload"]["tokens"].items() if t["is_shop"]][0]

    ws.send_json({"type": "place_token", "payload": {"token_id": "tok_buyer", "x": 2, "y": 1}})
    msg = ws.receive_json()

    ws.send_json({"type": "modify_value", "payload": {"token_id": "tok_buyer", "field": "gold", "delta": buyer_gold}})
    ws.receive_json()

    return shop_id, "tok_buyer"


def test_buy_item_success(auth_client, auth_setup, ws_room):
    token = auth_setup["admin_token"]
    auth_client.post("/api/items", json={
        "name": "治疗药水", "category": "consumable", "description": "", "effect_text": "", "price": 10,
    })
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        shop_id, buyer_id = _setup_shop_and_buyer(ws)

        ws.send_json({"type": "buy_item", "payload": {
            "buyer_token_id": buyer_id, "shop_token_id": shop_id, "item_name": "治疗药水",
        }})
        msg = ws.receive_json()
        assert msg["type"] == "item_bought"
        assert msg["payload"]["price"] == 10

        state = ws.receive_json()
        buyer = state["payload"]["tokens"][buyer_id]
        assert buyer["gold"] == 40
        assert "治疗药水" in buyer["backpack"]


def test_buy_item_insufficient_gold(auth_client, auth_setup, ws_room):
    token = auth_setup["admin_token"]
    auth_client.post("/api/items", json={
        "name": "传说神剑", "category": "weapon", "description": "", "effect_text": "", "price": 9999,
    })
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        shop_id, buyer_id = _setup_shop_and_buyer(ws, item_name="传说神剑", price=9999, buyer_gold=10)

        ws.send_json({"type": "buy_item", "payload": {
            "buyer_token_id": buyer_id, "shop_token_id": shop_id, "item_name": "传说神剑",
        }})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "金币不足" in msg["payload"]["message"]


def test_buy_item_not_in_shop_inventory(auth_client, auth_setup, ws_room):
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        shop_id, buyer_id = _setup_shop_and_buyer(ws, item_name="药水")

        ws.send_json({"type": "buy_item", "payload": {
            "buyer_token_id": buyer_id, "shop_token_id": shop_id, "item_name": "不存在的道具",
        }})
        msg = ws.receive_json()
        assert msg["type"] == "error"


def test_buy_item_from_non_shop_token_rejected(auth_client, auth_setup, ws_room):
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        ws.send_json({"type": "place_unit", "payload": {"unit_type": "monster", "name": "野狼", "x": 1, "y": 1}})
        msg = ws.receive_json()
        monster_id = list(msg["payload"]["tokens"].keys())[0]

        ws.send_json({"type": "place_token", "payload": {"token_id": "tok_buyer", "x": 2, "y": 1}})
        ws.receive_json()

        ws.send_json({"type": "buy_item", "payload": {
            "buyer_token_id": "tok_buyer", "shop_token_id": monster_id, "item_name": "随便",
        }})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "不是一个商店" in msg["payload"]["message"]


def test_buy_item_without_price_rejected(auth_client, auth_setup, ws_room):
    """道具库里没登记价格（或价格为0）的道具不能买，即便商店货架上挂了它。"""
    token = auth_setup["admin_token"]
    with auth_client.websocket_connect(f"/ws/{ws_room}?token={token}") as ws:
        ws.receive_json()
        shop_id, buyer_id = _setup_shop_and_buyer(ws, item_name="神秘道具")

        ws.send_json({"type": "buy_item", "payload": {
            "buyer_token_id": buyer_id, "shop_token_id": shop_id, "item_name": "神秘道具",
        }})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "未设置价格" in msg["payload"]["message"]
