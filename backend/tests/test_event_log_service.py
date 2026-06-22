import pytest
from app.services.event_log_service import EventLogService
from app.schemas.event import GameEvent


@pytest.fixture
def svc():
    return EventLogService()


def test_log_event(svc):
    e = GameEvent(timestamp=1, big_turn=1, sub_turn=0, actor="p1", action="move")
    svc.log(e)
    assert len(svc.get_all()) == 1


def test_get_by_turn(svc):
    svc.log(GameEvent(timestamp=1, big_turn=1, sub_turn=0, actor="p1", action="move"))
    svc.log(GameEvent(timestamp=2, big_turn=2, sub_turn=0, actor="p1", action="move"))
    assert len(svc.get_by_turn(1)) == 1
    assert len(svc.get_by_turn(2)) == 1


def test_clear(svc):
    svc.log(GameEvent(timestamp=1, big_turn=1, sub_turn=0, actor="p1", action="move"))
    svc.clear()
    assert len(svc.get_all()) == 0
