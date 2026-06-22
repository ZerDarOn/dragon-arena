import pytest
from app.services.room_service import RoomService


@pytest.fixture
def svc():
    return RoomService()


def test_create_room(svc):
    room = svc.create_room(name="Dragon#1", host_id="host1")
    assert room.name == "Dragon#1"
    assert "host1" in room.players
    assert room.players["host1"].is_host is True


def test_join_room(svc):
    room = svc.create_room(name="test", host_id="h1")
    svc.join_room(room.id, "p1", "Player1")
    assert "p1" in room.players
    assert room.players["p1"].nickname == "Player1"


def test_join_nonexistent_room(svc):
    result = svc.join_room("nonexistent", "p1", "Player1")
    assert result is None


def test_leave_room(svc):
    room = svc.create_room(name="test", host_id="h1")
    svc.join_room(room.id, "p1", "P1")
    svc.leave_room(room.id, "p1")
    assert room.players["p1"].is_connected is False


def test_get_room(svc):
    room = svc.create_room(name="test", host_id="h1")
    assert svc.get_room(room.id) is room


def test_list_rooms(svc):
    svc.create_room(name="r1", host_id="h1")
    svc.create_room(name="r2", host_id="h2")
    assert len(svc.list_rooms()) == 2
