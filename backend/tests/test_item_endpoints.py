"""Tests for /api/items/* — item library CRUD."""
import pytest


def _item_body(name="治疗药水", price=10):
    return {
        "name": name, "category": "consumable",
        "description": "恢复20点生命", "effect_text": "团主手动恢复20HP",
        "price": price,
    }


def test_admin_creates_and_lists_item(auth_client, auth_setup):
    r = auth_client.post("/api/items", json=_item_body())
    assert r.status_code == 200, r.text
    item = r.json()
    assert item["name"] == "治疗药水"
    assert item["price"] == 10

    r = auth_client.get("/api/items")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["id"] == item["id"]


def test_non_admin_cannot_create_item(client, auth_setup):
    token = auth_setup["user_token"]
    r = client.post("/api/items", json=_item_body(),
                     headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_non_admin_can_list_items(client, auth_setup):
    admin_token = auth_setup["admin_token"]
    client.post("/api/items", json=_item_body(),
                headers={"Authorization": f"Bearer {admin_token}"})
    user_token = auth_setup["user_token"]
    r = client.get("/api/items", headers={"Authorization": f"Bearer {user_token}"})
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_update_item(auth_client, auth_setup):
    item = auth_client.post("/api/items", json=_item_body()).json()
    r = auth_client.put(f"/api/items/{item['id']}", json={"price": 25})
    assert r.status_code == 200
    assert r.json()["price"] == 25
    assert r.json()["name"] == "治疗药水"  # 未传的字段不变


def test_delete_item(auth_client, auth_setup):
    item = auth_client.post("/api/items", json=_item_body()).json()
    r = auth_client.delete(f"/api/items/{item['id']}")
    assert r.status_code == 200
    assert auth_client.get("/api/items").json() == []


def test_filter_by_category(auth_client, auth_setup):
    auth_client.post("/api/items", json=_item_body("药水", price=5))
    auth_client.post("/api/items", json={
        "name": "长剑", "category": "weapon", "description": "", "effect_text": "", "price": 50,
    })
    r = auth_client.get("/api/items", params={"category": "weapon"})
    names = [i["name"] for i in r.json()]
    assert names == ["长剑"]
