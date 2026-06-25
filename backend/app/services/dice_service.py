import random
import re
from typing import List, Optional
from pydantic import BaseModel

MAX_DICE_COUNT = 100
MAX_SIDES = 1000


def _rand_int(a: int, b: int) -> int:
    return random.randint(a, b)


class DiceResult(BaseModel):
    value: int          # raw roll
    modifier: int = 0
    total: int = 0      # value + modifier
    crit_success: bool = False
    crit_fail: bool = False
    sides: int = 20


def roll_dice(
    sides: int = 20,
    modifier: int = 0,
    crit_success_threshold: int = 20,
    crit_fail_threshold: int = 1,
) -> DiceResult:
    """单颗骰子 + 固定修正。内部规则引擎（命中判定等）用这个，保持简单。"""
    sides = max(2, min(MAX_SIDES, int(sides)))
    raw = _rand_int(1, sides)
    return DiceResult(
        value=raw,
        modifier=modifier,
        total=raw + modifier,
        crit_success=(sides == 20 and raw >= crit_success_threshold),
        crit_fail=(sides == 20 and raw <= crit_fail_threshold),
        sides=sides,
    )


# ---------------------------------------------------------------------------
# 骰子表达式引擎（仿 FVTT）：支持 "2d20kh1+3"（优势）、"2d20kl1"（劣势）、
# "4d6kh3"（取最高3个，常见于属性生成）、"2d6+1d4+2"（多组骰子相加）等写法。
# ---------------------------------------------------------------------------

class DieRoll(BaseModel):
    sides: int
    value: int
    kept: bool = True   # False = 被 kh/kl 丢弃，不计入总和（前端仍展示，但置灰）


class DiceGroup(BaseModel):
    count: int
    sides: int
    keep: Optional[str] = None    # "h"（取最高） | "l"（取最低） | None
    keep_n: Optional[int] = None
    sign: int = 1                 # 该组结果计入总和时是 + 还是 -
    rolls: List[DieRoll] = []


class DiceExprResult(BaseModel):
    expression: str
    groups: List[DiceGroup] = []
    flat_modifier: int = 0
    value: int = 0       # 所有保留骰子的和（不含 flat_modifier），兼容旧版单骰字段
    modifier: int = 0    # = flat_modifier，兼容旧版单骰字段
    total: int = 0
    crit_success: bool = False   # 仅"单组单颗d20"（如 1d20+5）时才有意义
    crit_fail: bool = False
    sides: int = 20               # 兼容旧字段：仅单组单颗骰子时填真实面数


_TOKEN_RE = re.compile(
    r"(?P<sign>[+-])?\s*"
    r"(?:(?P<count>\d*)d(?P<sides>\d+)(?:k(?P<kf>[hl])(?P<kn>\d+))?|(?P<num>\d+))",
    re.IGNORECASE,
)


def roll_expression(
    expr: str,
    crit_success_threshold: int = 20,
    crit_fail_threshold: int = 1,
    forced_values: Optional[List[int]] = None,
) -> DiceExprResult:
    """解析并投掷一个骰子表达式。非法输入抛 ValueError（带可读中文提示），
    调用方（WS handler）已经有兜底的 try/except，会把 message 原样回传给客户端。

    forced_values: 仅供服务端内部/测试使用的"预定点数"（按表达式里骰子组的先后
    顺序拼平的一串数字），用于确定性测试或回放。**不接受来自客户端的点数**——骰子
    是服务端权威的（dice_service 摇 → 返回点数 → 前端用 3D 动画把这些点数演出来），
    这样既防作弊，又保证"骰子停的面"永远等于服务端算出的值。
    不提供时服务端照常自己随机。
    """
    cleaned = (expr or "").replace(" ", "")
    if not cleaned:
        raise ValueError("骰子表达式不能为空")
    if len(cleaned) > 64:
        raise ValueError("骰子表达式过长")

    forced_iter = iter(forced_values) if forced_values is not None else None

    pos = 0
    groups: List[DiceGroup] = []
    flat_modifier = 0
    matched_any = False

    for m in _TOKEN_RE.finditer(cleaned):
        if m.start() != pos:
            raise ValueError(f"无法解析骰子表达式：{expr}")
        pos = m.end()
        matched_any = True
        sign = -1 if m.group("sign") == "-" else 1

        if m.group("num") is not None:
            flat_modifier += sign * int(m.group("num"))
            continue

        count = int(m.group("count")) if m.group("count") else 1
        sides = int(m.group("sides"))
        if count < 1 or count > MAX_DICE_COUNT:
            raise ValueError(f"骰子数量必须在 1~{MAX_DICE_COUNT} 之间")
        if sides < 2 or sides > MAX_SIDES:
            raise ValueError(f"骰子面数必须在 2~{MAX_SIDES} 之间")

        kf = m.group("kf")
        kn = int(m.group("kn")) if m.group("kn") else None
        if kf and (kn is None or kn < 1 or kn > count):
            raise ValueError("保留骰子数量（kh/kl）不合法")

        rolls = []
        for _ in range(count):
            if forced_iter is not None:
                v = next(forced_iter, None)
                if v is None:
                    raise ValueError("提交的骰子点数数量与表达式不匹配")
                v = int(v)
                if v < 1 or v > sides:
                    raise ValueError(f"骰子点数 {v} 超出 d{sides} 的有效范围")
            else:
                v = _rand_int(1, sides)
            rolls.append(DieRoll(sides=sides, value=v))
        if kf:
            order = sorted(range(count), key=lambda i: rolls[i].value, reverse=(kf == "h"))
            keep_idx = set(order[:kn])
            for i, r in enumerate(rolls):
                r.kept = i in keep_idx

        groups.append(DiceGroup(count=count, sides=sides, keep=kf, keep_n=kn,
                                 sign=sign, rolls=rolls))

    if not matched_any or pos != len(cleaned):
        raise ValueError(f"无法解析骰子表达式：{expr}")
    if forced_iter is not None and next(forced_iter, None) is not None:
        raise ValueError("提交的骰子点数数量与表达式不匹配")

    kept_sum = sum(g.sign * sum(r.value for r in g.rolls if r.kept) for g in groups)
    total = kept_sum + flat_modifier

    is_single_d20 = (len(groups) == 1 and groups[0].sides == 20
                      and groups[0].count == 1 and groups[0].keep is None)
    crit_success = is_single_d20 and groups[0].rolls[0].value >= crit_success_threshold
    crit_fail = is_single_d20 and groups[0].rolls[0].value <= crit_fail_threshold
    sides_compat = groups[0].sides if len(groups) == 1 and groups[0].count == 1 else 20

    return DiceExprResult(
        expression=expr, groups=groups, flat_modifier=flat_modifier,
        value=kept_sum, modifier=flat_modifier, total=total,
        crit_success=crit_success, crit_fail=crit_fail, sides=sides_compat,
    )
