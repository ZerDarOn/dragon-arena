"""Tests for /characters/* endpoints, including secret_backups visibility rules."""
import pytest


def _create_sheet(client, token, name="Hero", secrets=None):
    body = {
        "name": name, "gender": "M", "profession": "战士",
        "talent": "刚毅", "hp_base": 120, "armor_base": 8, "ap_base": 3,
        "gold": 50, "backpack": ["potion"], "secret_backups": secrets or ["偷偷的底牌"],
    }
    r = client.post("/characters", json=body,
                    headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    return r.json()


def test_owner_creates_and_lists_sheet(auth_client, auth_setup):
    token = auth_setup["user_token"]
    sheet = _create_sheet(auth_client, token, name="MyHero", secrets=["s1", "s2"])
    sid = sheet["id"]
    assert sheet["secret_backups"] == ["s1", "s2"]

    r = auth_client.get("/characters", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    mine = r.json()
    assert len(mine) == 1
    assert mine[0]["id"] == sid
    # owner should see secrets
    assert mine[0]["secret_backups"] == ["s1", "s2"]


def test_owner_updates_sheet(auth_client, auth_setup):
    token = auth_setup["user_token"]
    sheet = _create_sheet(auth_client, token)
    sid = sheet["id"]
    body = {
        "name": "Renamed", "gender": "F", "profession": "法师",
        "talent": "智谋", "hp_base": 80, "armor_base": 3, "ap_base": 4,
        "gold": 100, "backpack": ["scroll"], "secret_backups": ["new_secret"],
    }
    r = auth_client.put(f"/characters/{sid}", json=body,
                        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["secret_backups"] == ["new_secret"]


def test_non_owner_cannot_update(auth_client, auth_setup):
    from app.services.auth_service import hash_password, create_token
    from app.deps import user_storage

    other = user_storage.create_user("other_user", hash_password("pw"))
    other_token = create_token(other.id, False)

    user_token = auth_setup["user_token"]
    sheet = _create_sheet(auth_client, user_token)

    r = auth_client.put(f"/characters/{sheet['id']}",
                        json={"name": "Hacked", "secret_backups": ["stolen"]},
                        headers={"Authorization": f"Bearer {other_token}"})
    assert r.status_code == 403


def test_secret_backups_hidden_from_others(auth_client, auth_setup):
    from app.services.auth_service import hash_password, create_token
    from app.deps import user_storage

    other = user_storage.create_user("snooper", hash_password("pw"))
    other_token = create_token(other.id, False)

    user_token = auth_setup["user_token"]
    sheet = _create_sheet(auth_client, user_token, secrets=["TOP_SECRET"])

    # Other user fetches this sheet
    r = auth_client.get(f"/characters/{sheet['id']}",
                        headers={"Authorization": f"Bearer {other_token}"})
    assert r.status_code == 200
    data = r.json()
    assert "secret_backups" not in data
    assert data["name"] == "Hero"


def test_admin_sees_full_sheet(auth_client, auth_setup):
    user_token = auth_setup["user_token"]
    admin_token = auth_setup["admin_token"]
    sheet = _create_sheet(auth_client, user_token, secrets=["ADMIN_CAN_SEE"])

    r = auth_client.get(f"/characters/{sheet['id']}",
                        headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["secret_backups"] == ["ADMIN_CAN_SEE"]


def test_owner_deletes_sheet(auth_client, auth_setup):
    token = auth_setup["user_token"]
    sheet = _create_sheet(auth_client, token)
    r = auth_client.delete(f"/characters/{sheet['id']}",
                           headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    # Confirm gone
    r = auth_client.get(f"/characters/{sheet['id']}",
                        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_unauth_cannot_access_characters(client):
    r = client.get("/characters")
    assert r.status_code == 401
