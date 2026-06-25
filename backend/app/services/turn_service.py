from app.schemas.room import Room, StateTag
from app.services.effect_resolver import EffectResolver
from typing import Dict
import random
import time


# Phase 3: 状态名 → 自描述字段映射（替代硬编码 if-elif）
# 扩展新状态只需加一行映射，无需改 effect_resolver 或 tick_states
STATE_PRESETS: Dict[str, dict] = {
    "撕裂": {"mode": "add", "target_field": "armor", "value": -2},
    "护甲降低": {"mode": "add", "target_field": "armor", "value": None},  # value 从 intensity 动态取
    "隐身": {"mode": None},
    "定身": {"mode": None},
    "沉默": {"mode": None},
    "点燃": {"dot_damage": 2},  # intensity 覆盖默认值
    "中毒": {"dot_damage": 3},
    "流血": {"dot_damage": 1},
    "毒圈": {"dot_damage": 0},  # 毒圈伤害由 apply_poison_circle 直接扣，状态只做标记
}


class TurnService:
    def __init__(self, room: Room):
        self.room = room
        self.effect_resolver = EffectResolver()

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
            self._award_survive_score()
        self.room.current_actor = self.room.turn_order[next_idx]

    def _award_survive_score(self) -> None:
        """大回合结束时，存活 token 获得 score_survive_per_turn 分。"""
        bonus = self.cfg.score_survive_per_turn
        for t in self.room.tokens.values():
            if not t.is_dead:
                t.score += bonus

    def _mark_dead(self, token) -> None:
        """统一处理死亡：设 is_dead + 记录淘汰顺序。"""
        token.is_dead = True
        self.record_elimination(token.id)

    def force_set_actor(self, token_id: str) -> None:
        if token_id in self.room.turn_order:
            self.room.current_actor = token_id

    def _regen_all_ap(self) -> None:
        for t in self.room.tokens.values():
            if not t.is_dead:
                t.ap = self.cfg.ap_regen

    def _tick_states(self) -> None:
        """每大回合 tick 一次状态：TTL 衰减 + 周期伤害 + 过期恢复。
        
        Phase 3：委托给 EffectResolver，不再硬编码状态名。
        """
        for t in self.room.tokens.values():
            if t.is_dead:
                continue
            hp_before = t.hp
            self.effect_resolver.tick_states(t)
            # tick 后检查致死（effect_resolver 设了 is_dead，这里补淘汰记录）
            if t.is_dead and hp_before > 0:
                self.record_elimination(t.id)

    def add_state(self, token_id: str, name: str, description: str, ttl: int, intensity: int = None) -> None:
        """为指定 token 添加状态（数据驱动，无硬编码）。
        
        Phase 3：根据 STATE_PRESETS 映射构造自描述 StateTag，委托给 EffectResolver。
        """
        token = self.room.tokens.get(token_id)
        if not token:
            return
        preset = STATE_PRESETS.get(name, {})
        # 构造 StateTag 字段
        mode = preset.get("mode")
        target_field = preset.get("target_field")
        dot_damage = preset.get("dot_damage", 0)
        value = preset.get("value")
        # intensity 覆盖：护甲降低的 value 动态取，点燃/中毒的 dot_damage 可被 intensity 覆盖
        if intensity is not None:
            if name in ("点燃", "中毒", "流血") and dot_damage > 0:
                dot_damage = intensity
            if name == "护甲降低" and value is None:
                value = -intensity
        state_id = f"s{int(time.time() * 1000)}"
        state = StateTag(
            id=state_id, name=name, description=description,
            ttl=ttl, intensity=intensity,
            mode=mode, target_field=target_field, value=value,
            dot_damage=dot_damage, source=name,
        )
        self.effect_resolver.apply_state(token, state)

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

    def record_elimination(self, token_id: str) -> None:
        """记录玩家淘汰顺序（先死者垫底）。"""
        if token_id not in self.room.elimination_order:
            self.room.elimination_order.append(token_id)

    def compute_final_ranking(self) -> Dict[str, int]:
        """计算最终总分 = 排名奖励 + 已有积分（存活+击杀）。

        排名顺序：最后存活者第1名，先死者垫底。
        套 ranking_table_8p 的分值。
        """
        ranking_table = self.cfg.ranking_table_8p
        all_token_ids = list(self.room.tokens.keys())
        # 淘汰顺序（先死者垫底）+ 仍存活者（冠军在前）
        survivors = [tid for tid in all_token_ids if tid not in self.room.elimination_order]
        # 名次顺序：存活者排前面（如果多个存活者，按 score 降序），然后 elimination_order 反向
        placement = survivors + list(reversed(self.room.elimination_order))
        result = {}
        for rank_idx, tid in enumerate(placement):
            base = self.room.tokens[tid].score
            rank_bonus = ranking_table[rank_idx] if rank_idx < len(ranking_table) else 0
            result[tid] = base + rank_bonus
        return result

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
                    self._mark_dead(t)
                self.add_state(t.id, "毒圈", f"在毒圈外，受到{damage}点伤害", 1)
