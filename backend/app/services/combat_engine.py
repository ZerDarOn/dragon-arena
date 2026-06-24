"""可扩展战斗规则引擎 — 通用触发器+效果系统。

设计原则：
- 不硬编码任何具体道具/技能/外挂
- 每个战斗动作 = 规则条目（触发条件 + 效果列表）
- 规则条目可通过 JSON/YAML 配置，无需改代码
- 支持：攻击、防御、移动、施法、使用道具、被动触发

规则原语：
  Trigger: 何时触发（手动/攻击时/命中时/受伤时/回合开始/HP低于...）
  Effect:  做什么（掷骰、修改HP、添加状态、移动、隐身等）
  Cost:    消耗什么（AP、使用次数）
"""

from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel
from app.schemas.room import Token, StateTag
from app.services.dice_service import roll_dice, DiceResult


# ---------------------------------------------------------------------------
# 触发条件
# ---------------------------------------------------------------------------

class Trigger(BaseModel):
    type: str  # manual | on_attack | on_hit | on_damage | on_turn_start | on_move | on_ap_spend | on_hp_below | on_death
    params: Dict[str, Any] = {}

    def match(self, context: "CombatContext") -> bool:
        """检查当前上下文是否满足触发条件。"""
        if self.type == "manual":
            return context.action == self.params.get("action")
        if self.type == "on_attack":
            return context.action == "attack"
        if self.type == "on_hit":
            return context.action == "attack" and context.hit_result and context.hit_result.is_hit
        if self.type == "on_damage":
            return context.action == "attack" and context.damage_result and context.damage_result.damage > 0
        if self.type == "on_turn_start":
            return context.action == "turn_start"
        if self.type == "on_move":
            return context.action == "move"
        if self.type == "on_ap_spend":
            return context.action == "ap_spend"
        if self.type == "on_hp_below":
            threshold = self.params.get("threshold", 0)
            return context.actor.hp <= threshold
        if self.type == "on_death":
            return context.target and context.target.is_dead
        return False


# ---------------------------------------------------------------------------
# 效果
# ---------------------------------------------------------------------------

class Effect(BaseModel):
    type: str  # roll_dice | modify_hp | modify_ap | modify_armor | add_state | remove_state | set_hidden | move | calc_hit | calc_damage | apply_damage
    params: Dict[str, Any] = {}

    def execute(self, context: "CombatContext") -> Dict[str, Any]:
        """执行效果，返回执行结果日志。"""
        result = {"type": self.type, "success": True}

        if self.type == "roll_dice":
            sides = self.params.get("sides", 20)
            modifier = self.params.get("modifier", 0)
            r = roll_dice(sides=sides, modifier=modifier)
            result["dice"] = r.model_dump()
            context.dice_results.append(r)

        elif self.type == "calc_hit":
            # 计算命中：D20 + bonus >= DC
            distance = self._get_distance(context)
            dc = self._get_dc_for_distance(distance, context)
            bonus = self.params.get("bonus", 0)
            # 取最后一次掷骰结果
            if not context.dice_results:
                r = roll_dice(sides=20, modifier=bonus)
                context.dice_results.append(r)
            else:
                r = context.dice_results[-1]
            total = r.total + bonus
            is_hit = total >= dc or r.crit_success
            is_miss = not is_hit and not r.crit_fail
            context.hit_result = HitResult(
                dc=dc, roll=r.value, bonus=bonus, total=total,
                is_hit=is_hit, is_crit=r.crit_success, is_fail=r.crit_fail,
            )
            result["hit"] = context.hit_result.model_dump()

        elif self.type == "calc_damage":
            # 计算伤害
            if not context.hit_result or not context.hit_result.is_hit:
                result["success"] = False
                result["reason"] = "未命中"
                return result
            base = self.params.get("base", 0)
            dice_expr = self.params.get("dice", "")  # 如 "D20-8"
            bonus = self.params.get("bonus", 0)
            damage = base + bonus
            if dice_expr:
                # 解析 D20-8 格式
                import re
                m = re.match(r'D(\d+)([+-]\d+)?', dice_expr)
                if m:
                    sides = int(m.group(1))
                    mod = int(m.group(2)) if m.group(2) else 0
                    # 取最后一次掷骰结果
                    if context.dice_results:
                        roll_val = context.dice_results[-1].value
                    else:
                        roll_val = roll_dice(sides=sides).value
                    damage += roll_val + mod
            # 计算实际伤害（扣甲）
            target = context.target
            if target:
                armor = target.armor
                # 检查目标是否有护甲减益状态
                for s in target.states:
                    if s.name == "撕裂" and s.ttl > 0:
                        armor = max(0, armor - 2)
                real_damage = max(0, damage - armor)
                context.damage_result = DamageResult(
                    raw_damage=damage, armor=armor, real_damage=real_damage,
                )
                result["damage"] = context.damage_result.model_dump()

        elif self.type == "apply_damage":
            # 应用伤害到目标
            if not context.damage_result:
                result["success"] = False
                result["reason"] = "无伤害可应用"
                return result
            target = context.target
            if target:
                target.hp -= context.damage_result.real_damage
                if target.hp <= 0:
                    target.hp = 0
                    target.is_dead = True
                result["hp_after"] = target.hp
                result["is_dead"] = target.is_dead

        elif self.type == "modify_hp":
            delta = self.params.get("delta", 0)
            target = context.target or context.actor
            target.hp = max(0, min(target.max_hp, target.hp + delta))
            result["hp_after"] = target.hp

        elif self.type == "modify_ap":
            delta = self.params.get("delta", 0)
            target = context.target or context.actor
            target.ap = max(0, min(target.max_ap, target.ap + delta))
            result["ap_after"] = target.ap

        elif self.type == "modify_armor":
            delta = self.params.get("delta", 0)
            target = context.target or context.actor
            target.armor = max(0, target.armor + delta)
            result["armor_after"] = target.armor

        elif self.type == "add_state":
            name = self.params.get("name", "")
            description = self.params.get("description", "")
            ttl = self.params.get("ttl", 1)
            intensity = self.params.get("intensity")
            target = context.target or context.actor
            state_id = f"s{int(time.time() * 1000)}"
            target.states.append(StateTag(
                id=state_id, name=name, description=description,
                ttl=ttl, intensity=intensity,
            ))
            result["state_id"] = state_id

        elif self.type == "remove_state":
            name = self.params.get("name", "")
            target = context.target or context.actor
            target.states = [s for s in target.states if s.name != name]
            result["removed"] = name

        elif self.type == "set_hidden":
            hidden = self.params.get("hidden", True)
            target = context.target or context.actor
            target.is_hidden = hidden
            result["is_hidden"] = hidden

        elif self.type == "move":
            dx = self.params.get("dx", 0)
            dy = self.params.get("dy", 0)
            target = context.target or context.actor
            if target.position:
                target.position["x"] += dx
                target.position["y"] += dy
            result["position"] = target.position

        return result

    def _get_distance(self, context: "CombatContext") -> int:
        """计算 actor 到 target 的切比雪夫距离。"""
        a = context.actor
        t = context.target
        if not a or not t or not a.position or not t.position:
            return 0
        return max(abs(a.position["x"] - t.position["x"]), abs(a.position["y"] - t.position["y"]))

    def _get_dc_for_distance(self, distance: int, context: "CombatContext") -> int:
        """根据距离返回 DC。"""
        cfg = context.room_config
        if distance <= 2:
            return cfg.dc_melee
        elif distance <= 6:
            return cfg.dc_mid
        else:
            return cfg.dc_ranged


# ---------------------------------------------------------------------------
# 规则条目
# ---------------------------------------------------------------------------

class RuleEntry(BaseModel):
    name: str
    triggers: List[Trigger]
    effects: List[Effect]
    cost: Dict[str, Any] = {}  # {ap: int, uses: int, uses_per_battle: int}

    def can_trigger(self, context: "CombatContext") -> bool:
        """检查是否满足触发条件。"""
        return any(t.match(context) for t in self.triggers)

    def execute(self, context: "CombatContext") -> List[Dict[str, Any]]:
        """执行所有效果，返回效果日志列表。"""
        results = []
        # 检查消耗
        ap_cost = self.cost.get("ap", 0)
        if ap_cost > 0 and context.actor.ap < ap_cost:
            return [{"type": "cost_check", "success": False, "reason": "AP不足"}]
        # 扣除消耗
        if ap_cost > 0:
            context.actor.ap -= ap_cost
            results.append({"type": "cost_ap", "delta": -ap_cost, "ap_after": context.actor.ap})
        # 执行效果
        for effect in self.effects:
            results.append(effect.execute(context))
        return results


# ---------------------------------------------------------------------------
# 战斗上下文
# ---------------------------------------------------------------------------

class HitResult(BaseModel):
    dc: int
    roll: int
    bonus: int
    total: int
    is_hit: bool
    is_crit: bool
    is_fail: bool


class DamageResult(BaseModel):
    raw_damage: int
    armor: int
    real_damage: int


class CombatContext(BaseModel):
    action: str  # attack | defend | move | turn_start | ap_spend | use_item | manual
    actor: Token
    target: Optional[Token] = None
    room_config: Any = None  # RoomConfig
    dice_results: List[DiceResult] = []
    hit_result: Optional[HitResult] = None
    damage_result: Optional[DamageResult] = None

    class Config:
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# 规则引擎
# ---------------------------------------------------------------------------

class CombatEngine:
    """战斗规则引擎：管理所有规则条目，执行战斗动作。"""

    def __init__(self):
        self.rules: Dict[str, List[RuleEntry]] = {}  # token_id -> [RuleEntry]
        self.global_rules: List[RuleEntry] = []  # 全局规则（如毒圈、环境效果）

    def register_rules(self, token_id: str, entries: List[RuleEntry]):
        """为某个 token 注册规则条目。"""
        self.rules[token_id] = entries

    def add_global_rule(self, entry: RuleEntry):
        """添加全局规则。"""
        self.global_rules.append(entry)

    def execute_action(self, context: CombatContext) -> Dict[str, Any]:
        """执行一个战斗动作，返回完整战斗日志。"""
        log = {
            "action": context.action,
            "actor_id": context.actor.id,
            "target_id": context.target.id if context.target else None,
            "results": [],
        }

        # 1. 执行 actor 的匹配规则
        actor_rules = self.rules.get(context.actor.id, [])
        for rule in actor_rules:
            if rule.can_trigger(context):
                rule_results = rule.execute(context)
                log["results"].append({"rule": rule.name, "effects": rule_results})

        # 2. 执行 target 的被动规则（如反伤、闪避）
        if context.target:
            target_rules = self.rules.get(context.target.id, [])
            for rule in target_rules:
                if rule.can_trigger(context):
                    rule_results = rule.execute(context)
                    log["results"].append({"rule": rule.name, "effects": rule_results, "passive": True})

        # 3. 执行全局规则
        for rule in self.global_rules:
            if rule.can_trigger(context):
                rule_results = rule.execute(context)
                log["results"].append({"rule": rule.name, "effects": rule_results, "global": True})

        return log


# ---------------------------------------------------------------------------
# 便捷函数：创建标准战斗规则
# ---------------------------------------------------------------------------

def create_attack_rule(name: str, range_type: str, base_damage: int, dice_expr: str = "",
                       bonus: int = 0, ap_cost: int = 1) -> RuleEntry:
    """创建一个标准攻击规则条目。"""
    return RuleEntry(
        name=name,
        triggers=[Trigger(type="manual", params={"action": "attack", "range": range_type})],
        effects=[
            Effect(type="roll_dice", params={"sides": 20, "modifier": 0}),
            Effect(type="calc_hit", params={"bonus": bonus}),
            Effect(type="calc_damage", params={"base": base_damage, "dice": dice_expr, "bonus": 0}),
            Effect(type="apply_damage", params={}),
        ],
        cost={"ap": ap_cost},
    )


def create_defend_rule(name: str, ap_cost: int = 1) -> RuleEntry:
    """创建一个防御规则（察觉检定）。"""
    return RuleEntry(
        name=name,
        triggers=[Trigger(type="manual", params={"action": "defend"})],
        effects=[
            Effect(type="roll_dice", params={"sides": 20, "modifier": 0}),
            # 防御效果：减少下次受到的伤害（由 DM 手动处理或后续扩展）
        ],
        cost={"ap": ap_cost},
    )


def create_status_rule(name: str, status_name: str, ttl: int, description: str,
                       trigger_type: str = "on_hit", trigger_params: Dict = None) -> RuleEntry:
    """创建一个状态添加规则（如撕裂、点燃）。"""
    return RuleEntry(
        name=name,
        triggers=[Trigger(type=trigger_type, params=trigger_params or {})],
        effects=[
            Effect(type="add_state", params={"name": status_name, "ttl": ttl, "description": description}),
        ],
        cost={},
    )


import time
