"""通用 effect resolver — 数据驱动的状态应用/移除/tick。

替代 turn_service._tick_states 和 token_service.tick_states 的硬编码 if-elif。
设计参考 FVTT ActiveEffect：
- apply 时根据 mode 修改属性
- remove 时执行逆操作（add 的逆是减，multiply 的逆是除，override 的逆是恢复原值）
- tick 时通用处理 dot_damage + TTL 衰减 + 过期移除
"""
import time
from app.schemas.room import Token, StateTag


class EffectResolver:
    """数据驱动的状态效果解析器。"""

    def apply_state(self, token: Token, state: StateTag) -> None:
        """应用状态到 token。根据 mode 修改属性，记录 original_value。"""
        # 记录来源和应用前原值（override 模式恢复用）
        if state.mode == "override" and state.target_field:
            current = getattr(token, state.target_field, None)
            if current is not None:
                state.original_value = current
                setattr(token, state.target_field, state.value)
        elif state.mode == "add" and state.target_field:
            current = getattr(token, state.target_field, None)
            if current is not None:
                state.original_value = current
                setattr(token, state.target_field, current + state.value)
        elif state.mode == "multiply" and state.target_field:
            current = getattr(token, state.target_field, None)
            if current is not None:
                state.original_value = current
                setattr(token, state.target_field, current * state.value)

        # 特殊标记类状态（mode=None 但有业务语义）
        self._apply_marker(token, state)

        # 去重：同名状态先移除旧的（保持刷新语义）
        token.states = [s for s in token.states if s.name != state.name]
        token.states.append(state)

    def remove_state(self, token: Token, state: StateTag) -> None:
        """移除状态，执行逆操作恢复属性。"""
        if state.mode == "add" and state.target_field:
            current = getattr(token, state.target_field, None)
            if current is not None:
                setattr(token, state.target_field, current - state.value)
        elif state.mode == "multiply" and state.target_field:
            current = getattr(token, state.target_field, None)
            if current is not None and state.value != 0:
                setattr(token, state.target_field, current / state.value)
        elif state.mode == "override" and state.target_field:
            if state.original_value is not None:
                setattr(token, state.target_field, state.original_value)

        # 特殊标记类状态的逆操作
        self._remove_marker(token, state)

        # 从 token.states 移除
        token.states = [s for s in token.states if s.id != state.id]

    def tick_states(self, token: Token) -> None:
        """tick 所有状态：周期伤害 + TTL 衰减 + 过期移除。"""
        if token.is_dead:
            return
        kept = []
        for s in token.states:
            # 1. 周期伤害（dot_damage > 0 时每 tick 扣 HP）
            if s.dot_damage and s.dot_damage > 0:
                token.hp = max(0, token.hp - s.dot_damage)
                if token.hp <= 0:
                    token.is_dead = True

            # 2. TTL 衰减
            s.ttl -= 1

            # 3. 过期处理
            if s.ttl <= 0:
                # 恢复属性（逆操作）
                self._revert_attribute(token, s)
            else:
                kept.append(s)
        token.states = kept

    def _revert_attribute(self, token: Token, state: StateTag) -> None:
        """状态过期时的属性恢复（逆操作），不调 _remove_marker（状态已从列表移除）。"""
        if state.mode == "add" and state.target_field:
            current = getattr(token, state.target_field, None)
            if current is not None:
                setattr(token, state.target_field, current - state.value)
        elif state.mode == "multiply" and state.target_field:
            current = getattr(token, state.target_field, None)
            if current is not None and state.value != 0:
                setattr(token, state.target_field, current / state.value)
        elif state.mode == "override" and state.target_field:
            if state.original_value is not None:
                setattr(token, state.target_field, state.original_value)

        # 特殊标记的恢复
        self._remove_marker(token, state)

    def _apply_marker(self, token: Token, state: StateTag) -> None:
        """特殊标记类状态的立即应用（隐身/沉默/定身等）。"""
        name = state.name
        if name == "隐身":
            token.is_hidden = True
        elif name in ("沉默", "定身"):
            token.ap = 0

    def _remove_marker(self, token: Token, state: StateTag) -> None:
        """特殊标记类状态的恢复。"""
        name = state.name
        if name == "隐身":
            token.is_hidden = False
        # 沉默/定身不恢复 AP（AP 由回合开始时 _regen_all_ap 处理）
