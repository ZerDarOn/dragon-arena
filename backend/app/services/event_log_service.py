import json
from typing import List
from app.schemas.event import GameEvent


class EventLogService:
    def __init__(self):
        self.events: List[GameEvent] = []

    def log(self, event: GameEvent) -> None:
        self.events.append(event)

    def get_all(self) -> List[GameEvent]:
        return list(self.events)

    def get_by_turn(self, big_turn: int) -> List[GameEvent]:
        return [e for e in self.events if e.big_turn == big_turn]

    def clear(self) -> None:
        self.events = []

    def export_json(self) -> str:
        return json.dumps([e.model_dump() for e in self.events], ensure_ascii=False, indent=2)
