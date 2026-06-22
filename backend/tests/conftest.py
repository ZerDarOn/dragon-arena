import os
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def temp_db(monkeypatch):
    """Use a temp SQLite DB for each test to isolate state."""
    # NOTE: deps module already imported user_storage; we must reset its db_path
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # Patch env BEFORE re-importing deps; but deps is already loaded, so re-init
    from app.services.user_storage import UserStorage
    from app.deps import user_storage as global_storage
    global_storage.db_path = path
    global_storage._init_schema()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_setup(temp_db):
    """Create an admin + a normal user, return (admin_token, user_token, admin_client, user_client)."""
    from app.services.auth_service import hash_password, create_token
    from app.deps import user_storage
    from app.main import app

    admin = user_storage.create_user("admin_test", hash_password("pw"), is_admin=True)
    user = user_storage.create_user("user_test", hash_password("pw"), is_admin=False)
    admin_token = create_token(admin.id, True)
    user_token = create_token(user.id, False)
    return {
        "admin_id": admin.id,
        "user_id": user.id,
        "admin_token": admin_token,
        "user_token": user_token,
    }


@pytest.fixture
def auth_client(client, auth_setup):
    """A TestClient that automatically sends admin bearer token."""
    client.headers.update({"Authorization": f"Bearer {auth_setup['admin_token']}"})
    return client
