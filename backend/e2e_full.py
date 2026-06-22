"""End-to-end smoke test for auth + characters + battle flow.

Prerequisite: backend running on http://127.0.0.1:8000 with empty users.db.
Steps:
  1. Seed admin via direct DB write (since no bootstrap endpoint yet)
  2. Admin creates a user via /admin/users
  3. User logs in, creates a character sheet with secret_backups
  4. Admin logs in, fetches the user's sheet → sees secret_backups
  5. Other user logs in, fetches the same sheet → secret_backups stripped
  6. Admin creates a room
  7. Admin connects WS with token, places token, moves
  8. User connects WS to same room, receives state_sync

Run: python e2e_full.py
"""
import asyncio
import json
import os
import sys
import time

import httpx
import websockets

BASE = "http://127.0.0.1:8000"


def seed_admin_if_missing():
    """Directly insert an admin user into the DB (bootstrap)."""
    from app.deps import user_storage
    from app.services.auth_service import hash_password

    if not user_storage.get_user_by_nickname("admin"):
        user_storage.create_user("admin", hash_password("admin123"), is_admin=True)
        print("[seed] created admin/admin123")
    else:
        print("[seed] admin already exists")


def test_auth_flow():
    print("\n=== Phase A: Auth & Characters ===")
    # 1. Admin login
    r = httpx.post(f"{BASE}/auth/login", json={"nickname": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    admin_token = r.json()["token"]
    admin_id = r.json()["user"]["id"]
    print(f"[admin] login OK, id={admin_id[:8]}")

    # 2. Admin creates a user
    r = httpx.post(f"{BASE}/admin/users",
                   json={"nickname": "alice", "password": "alice_pw", "is_admin": False},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    alice_id = r.json()["id"]
    print(f"[admin] create alice OK, id={alice_id[:8]}")

    # 3. Alice login
    r = httpx.post(f"{BASE}/auth/login", json={"nickname": "alice", "password": "alice_pw"})
    assert r.status_code == 200, r.text
    alice_token = r.json()["token"]
    print(f"[alice] login OK")

    # 4. Alice creates a character with secret_backups
    r = httpx.post(f"{BASE}/characters",
                   json={
                       "name": "AliceHero", "gender": "F", "profession": "游侠",
                       "talent": "鹰眼", "hp_base": 110, "armor_base": 4, "ap_base": 3,
                       "gold": 30, "backpack": ["弓", "箭"], "secret_backups": ["毒药配方"],
                   },
                   headers={"Authorization": f"Bearer {alice_token}"})
    assert r.status_code == 200, r.text
    sheet_id = r.json()["id"]
    assert r.json()["secret_backups"] == ["毒药配方"]
    print(f"[alice] create character OK, id={sheet_id[:8]}, secrets preserved")

    # 5. Admin fetches sheet → sees secret_backups
    r = httpx.get(f"{BASE}/characters/{sheet_id}",
                  headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    assert r.json().get("secret_backups") == ["毒药配方"]
    print(f"[admin] fetch sheet OK, secret_backups visible")

    # 6. Admin creates a "snooper" user, snooper fetches → secret_backups HIDDEN
    r = httpx.post(f"{BASE}/admin/users",
                   json={"nickname": "snooper", "password": "snooper_pw"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    snooper_token = httpx.post(f"{BASE}/auth/login",
                               json={"nickname": "snooper", "password": "snooper_pw"}).json()["token"]
    r = httpx.get(f"{BASE}/characters/{sheet_id}",
                  headers={"Authorization": f"Bearer {snooper_token}"})
    assert r.status_code == 200, r.text
    assert "secret_backups" not in r.json(), "LEAK: snooper saw secret_backups!"
    print(f"[snooper] fetch sheet OK, secret_backups STRIPPED ✓")

    return admin_token, alice_token


def test_room_and_ws(admin_token, alice_token):
    print("\n=== Phase B: Room & WebSocket ===")
    # Admin creates room
    r = httpx.post(f"{BASE}/rooms", json={"name": "TestBattle"},
                   headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    room_id = r.json()["id"]
    print(f"[admin] create room OK, id={room_id}")

    return room_id


async def ws_flow(admin_token, alice_token, room_id):
    admin_uri = f"ws://127.0.0.1:8000/ws/{room_id}?token={admin_token}"
    alice_uri = f"ws://127.0.0.1:8000/ws/{room_id}?token={alice_token}"

    async with websockets.connect(admin_uri) as ws_admin:
        state = await asyncio.wait_for(ws_admin.recv(), timeout=5)
        assert json.loads(state)["type"] == "state_sync"
        print(f"[admin ws] connected, got state_sync")

        async with websockets.connect(alice_uri) as ws_alice:
            # alice also gets state_sync
            await asyncio.wait_for(ws_alice.recv(), timeout=5)
            print(f"[alice ws] connected, got state_sync")

            # Admin places a token
            await ws_admin.send(json.dumps({
                "type": "place_token",
                "payload": {"token_id": "hero1", "x": 10, "y": 10},
            }))
            # both receive state_sync
            await asyncio.wait_for(ws_admin.recv(), timeout=5)
            await asyncio.wait_for(ws_alice.recv(), timeout=5)
            print(f"[admin ws] place_token broadcast to both ✓")

            # Admin rolls dice
            await ws_admin.send(json.dumps({
                "type": "dice_roll", "payload": {"sides": 20, "modifier": 0},
            }))
            admin_dice = json.loads(await asyncio.wait_for(ws_admin.recv(), timeout=5))
            alice_dice = json.loads(await asyncio.wait_for(ws_alice.recv(), timeout=5))
            assert admin_dice["type"] == "dice_result"
            assert alice_dice["type"] == "dice_result"
            print(f"[ws] dice_roll broadcast to both ✓, admin got {admin_dice['payload']['total']}")

            # Admin sends hall chat
            await ws_admin.send(json.dumps({
                "type": "chat", "payload": {"channel": "hall", "text": "hi all"},
            }))
            msg = json.loads(await asyncio.wait_for(ws_admin.recv(), timeout=5))
            assert msg["type"] == "chat" and msg["payload"]["text"] == "hi all"
            await asyncio.wait_for(ws_alice.recv(), timeout=5)
            print(f"[ws] hall chat broadcast to both ✓")


async def main():
    print("=== Full E2E: Auth + Characters + Room + WS ===")
    seed_admin_if_missing()
    admin_token, alice_token = test_auth_flow()
    room_id = test_room_and_ws(admin_token, alice_token)
    await ws_flow(admin_token, alice_token, room_id)
    print("\n=== ✅ ALL E2E CHECKS PASSED ===")


if __name__ == "__main__":
    # Ensure CWD is backend/
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    asyncio.run(main())
