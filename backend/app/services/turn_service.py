from app.schemas.room import Room


class TurnService:
    def __init__(self, room: Room):
        self.room = room
        self.cfg = room.config

    def set_order(self, token_ids: list) -> None:
        self.room.turn_order = list(token_ids)

    def start(self) -> None:
        if not self.room.turn_order:
            return
        self.room.big_turn = 1
        self.room.sub_turn = 0
        self.room.current_actor = self.room.turn_order[0]
        self._regen_all_ap()

    def end_turn(self) -> None:
        if not self.room.turn_order or not self.room.current_actor:
            return
        idx = self.room.turn_order.index(self.room.current_actor)
        next_idx = (idx + 1) % len(self.room.turn_order)
        self.room.sub_turn += 1
        if next_idx == 0:
            self.room.big_turn += 1
            self._regen_all_ap()
            self._tick_states()
        self.room.current_actor = self.room.turn_order[next_idx]

    def force_set_actor(self, token_id: str) -> None:
        if token_id in self.room.turn_order:
            self.room.current_actor = token_id

    def _regen_all_ap(self) -> None:
        for t in self.room.tokens.values():
            if not t.is_dead:
                t.ap = self.cfg.ap_regen

    def _tick_states(self) -> None:
        for t in self.room.tokens.values():
            kept = []
            for s in t.states:
                s.ttl -= 1
                if s.ttl > 0:
                    kept.append(s)
            t.states = kept
