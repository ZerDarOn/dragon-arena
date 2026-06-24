from app.schemas.room import Room, StateTag
import random
import time


class TurnService:
    def __init__(self, room: Room):
        self.room = room

    @property
    def cfg(self):
        return self.room.config

    def set_order(self, token_ids: list) -> None:
        self.room.turn_order = list(token_ids)

    def shuffle_order(self, token_ids: list = None) -> list:
        """Shuffle token order. If ids not provided, use all living tokens."""
        if token_ids is None:
            token_ids = [t.id for t in self.room.tokens.values() if not t.is_dead]
        shuffled = list(token_ids)
        random.shuffle(shuffled)
        self.room.turn_order = shuffled
        return shuffled

    def start(self) -> None:
        if not self.room.turn_order:
            return
        self.room.big_turn = 1
        self.room.sub_turn = 0
        self.room.current_actor = self.room.turn_order[0]
        self._regen_all_ap()
        # 初始化毒圈半径
        self.cfg.poison_circle_radius = max(self.cfg.map_width, self.cfg.map_height) // 2

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
            self.apply_poison_circle()
        self.room.current_actor = self.room.turn_order[next_idx]

    def force_set_actor(self, token_id: str) -> None:
        if token_id in self.room.turn_order:
            self.room.current_actor = token_id

    def _regen_all_ap(self) -> None:
        for t in self.room.tokens.values():
            if not t.is_dead:
                t.ap = self.cfg.ap_regen

    def _tick_states(self) -> None:
        """每大回合 tick 一次状态：TTL 衰减 + 周期性效果触发。"""
        for t in self.room.tokens.values():
            if t.is_dead:
                continue
            kept = []
            for s in t.states:
                s.ttl -= 1
                # 触发周期性效果
                if s.name == "点燃" and s.ttl > 0:
                    damage = s.intensity or 2
                    t.hp = max(0, t.hp - damage)
                    if t.hp <= 0:
                        t.is_dead = True
                elif s.name == "中毒" and s.ttl > 0:
                    damage = s.intensity or 3
                    t.hp = max(0, t.hp - damage)
                    if t.hp <= 0:
                        t.is_dead = True
                elif s.name == "流血" and s.ttl > 0:
                    damage = s.intensity or 1
                    t.hp = max(0, t.hp - damage)
                    if t.hp <= 0:
                        t.is_dead = True
                # 保留未过期的状态
                if s.ttl > 0:
                    kept.append(s)
                else:
                    # 状态过期时恢复属性
                    if s.name == "撕裂":
                        t.armor = min(t.armor + 2, 5)
                    elif s.name == "隐身":
                        t.is_hidden = False
                    elif s.name == "护甲降低":
                        t.armor = min(t.armor + (s.intensity or 2), 5)
            t.states = kept

    def add_state(self, token_id: str, name: str, description: str, ttl: int, intensity: int = None) -> None:
        """为指定 token 添加状态。"""
        token = self.room.tokens.get(token_id)
        if not token:
            return
        # 去重：同名状态刷新 TTL
        token.states = [s for s in token.states if s.name != name]
        state_id = f"s{int(time.time() * 1000)}"
        token.states.append(StateTag(
            id=state_id, name=name, description=description,
            ttl=ttl, intensity=intensity,
        ))
        # 立即应用状态效果
        if name == "撕裂":
            token.armor = max(0, token.armor - 2)
        elif name == "隐身":
            token.is_hidden = True
        elif name == "护甲降低":
            token.armor = max(0, token.armor - (intensity or 2))
        elif name == "定身":
            # 定身：AP 置 0，不能移动
            token.ap = 0
        elif name == "沉默":
            # 沉默：AP 置 0，不能施法/使用技能
            token.ap = 0

    def set_poison_circle(self, center_x: int = None, center_y: int = None, radius: int = None, enabled: bool = None) -> None:
        """手动设置毒圈参数。"""
        if center_x is not None:
            self.cfg.poison_circle_center_x = center_x
        if center_y is not None:
            self.cfg.poison_circle_center_y = center_y
        if radius is not None:
            self.cfg.poison_circle_radius = radius
        if enabled is not None:
            self.cfg.poison_circle_enabled = enabled

    def apply_poison_circle(self) -> None:
        """毒圈伤害：每大回合收缩并伤害圈外玩家。"""
        if not getattr(self.cfg, 'poison_circle_enabled', True):
            return
        max_radius = max(self.cfg.map_width, self.cfg.map_height) // 2
        min_radius = self.cfg.poison_circle_min_radius
        shrink_per_turn = self.cfg.poison_circle_shrink_per_turn
        current_radius = max(min_radius, max_radius - self.room.big_turn * shrink_per_turn)
        self.cfg.poison_circle_radius = current_radius
        
        center_x = getattr(self.cfg, 'poison_circle_center_x', self.cfg.map_width // 2)
        center_y = getattr(self.cfg, 'poison_circle_center_y', self.cfg.map_height // 2)
        
        for t in self.room.tokens.values():
            if t.is_dead or not t.position:
                continue
            dist = max(abs(t.position["x"] - center_x), abs(t.position["y"] - center_y))
            if dist > current_radius:
                damage = self.cfg.poison_circle_damage_base + (dist - current_radius) * self.cfg.poison_circle_damage_per_dist
                t.hp = max(0, t.hp - damage)
                if t.hp <= 0:
                    t.is_dead = True
                self.add_state(t.id, "毒圈", f"在毒圈外，受到{damage}点伤害", 1)
