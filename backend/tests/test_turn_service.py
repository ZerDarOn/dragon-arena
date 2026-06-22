import pytest
from app.services.turn_service import TurnService
from app.schemas.room import Room, Token


@pytest.fixture
def setup():
    room = Room(id="r1", name="test")
    for i in range(1, 5):
        room.tokens[f"t{i}"] = Token(id=f"t{i}", owner_id=f"p{i}")
    svc = TurnService(room)
    return svc, room


def test_set_order(setup):
    svc, room = setup
    svc.set_order(["t3", "t1", "t4", "t2"])
    assert room.turn_order == ["t3", "t1", "t4", "t2"]


def test_start_first_turn(setup):
    svc, room = setup
    svc.set_order(["t3", "t1", "t4", "t2"])
    svc.start()
    assert room.current_actor == "t3"
    assert room.big_turn == 1


def test_end_turn_advances(setup):
    svc, room = setup
    svc.set_order(["t3", "t1", "t4", "t2"])
    svc.start()
    svc.end_turn()
    assert room.current_actor == "t1"


def test_end_turn_wraps_big_turn(setup):
    svc, room = setup
    svc.set_order(["t3", "t1", "t4", "t2"])
    svc.start()
    for _ in range(4):
        svc.end_turn()
    assert room.current_actor == "t3"
    assert room.big_turn == 2


def test_ap_regen_on_big_turn(setup):
    svc, room = setup
    svc.set_order(["t3", "t1", "t4", "t2"])
    svc.start()
    room.tokens["t3"].ap = 0
    for _ in range(4):
        svc.end_turn()
    assert room.tokens["t3"].ap == room.config.ap_regen


def test_force_set_actor(setup):
    svc, room = setup
    svc.set_order(["t3", "t1", "t4", "t2"])
    svc.start()
    svc.force_set_actor("t2")
    assert room.current_actor == "t2"
