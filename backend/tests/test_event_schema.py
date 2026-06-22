from app.schemas.event import GameEvent


def test_event_basic():
    e = GameEvent(
        timestamp=1000, big_turn=1, sub_turn=3,
        actor="p1", action="move", target="t1",
        params={"from": {"x": 1, "y": 1}, "to": {"x": 2, "y": 1}},
    )
    assert e.action == "move"
    assert e.params["to"] == {"x": 2, "y": 1}
