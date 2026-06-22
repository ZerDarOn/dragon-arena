"""Tests for /auth/* endpoints."""
import pytest


def test_login_success(client, auth_setup):
    r = client.post("/auth/login", json={"nickname": "admin_test", "password": "pw"})
    assert r.status_code == 200
    data = r.json()
    assert "token" in data and isinstance(data["token"], str)
    assert data["user"]["nickname"] == "admin_test"
    assert data["user"]["is_admin"] is True
    assert "password_hash" not in data["user"]


def test_login_wrong_password(client, auth_setup):
    r = client.post("/auth/login", json={"nickname": "admin_test", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client, auth_setup):
    r = client.post("/auth/login", json={"nickname": "ghost", "password": "pw"})
    assert r.status_code == 401


def test_me_with_token(client, auth_setup):
    token = auth_setup["user_token"]
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["nickname"] == "user_test"
    assert r.json()["is_admin"] is False


def test_me_without_token(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_me_with_invalid_token(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401


# ---- /admin/users ----

def test_admin_create_user_as_admin(auth_client):
    r = auth_client.post("/admin/users", json={"nickname": "newbie", "password": "secret", "is_admin": False})
    assert r.status_code == 200
    data = r.json()
    assert data["nickname"] == "newbie"
    assert data["is_admin"] is False
    assert "password_hash" not in data


def test_admin_create_duplicate_nickname(auth_client):
    auth_client.post("/admin/users", json={"nickname": "dup", "password": "x"})
    r = auth_client.post("/admin/users", json={"nickname": "dup", "password": "y"})
    assert r.status_code == 409


def test_admin_list_users(auth_client):
    auth_client.post("/admin/users", json={"nickname": "u1", "password": "x"})
    auth_client.post("/admin/users", json={"nickname": "u2", "password": "x"})
    r = auth_client.get("/admin/users")
    assert r.status_code == 200
    nicks = {u["nickname"] for u in r.json()}
    assert {"admin_test", "user_test", "u1", "u2"}.issubset(nicks)


def test_admin_delete_user(auth_client):
    r = auth_client.post("/admin/users", json={"nickname": "to_del", "password": "x"})
    uid = r.json()["id"]
    r = auth_client.delete(f"/admin/users/{uid}")
    assert r.status_code == 200
    # Verify gone
    r = auth_client.get("/admin/users")
    assert all(u["id"] != uid for u in r.json())


def test_non_admin_cannot_access_admin(client, auth_setup):
    """User token cannot hit /admin/users."""
    token = auth_setup["user_token"]
    r = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_unauth_cannot_access_admin(client):
    r = client.get("/admin/users")
    assert r.status_code == 401


def test_new_user_can_login(auth_client):
    """End-to-end: admin creates user, that user can login."""
    auth_client.post("/admin/users", json={"nickname": "verify_me", "password": "abc123"})
    # Strip auth header to simulate a fresh client
    saved = auth_client.headers.pop("Authorization", None)
    try:
        r = auth_client.post("/auth/login", json={"nickname": "verify_me", "password": "abc123"})
        assert r.status_code == 200
        assert "token" in r.json()
    finally:
        if saved:
            auth_client.headers["Authorization"] = saved
