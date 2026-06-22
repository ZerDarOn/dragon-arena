import random
from pydantic import BaseModel


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
    raw = _rand_int(1, sides)
    return DiceResult(
        value=raw,
        modifier=modifier,
        total=raw + modifier,
        crit_success=(sides == 20 and raw >= crit_success_threshold),
        crit_fail=(sides == 20 and raw <= crit_fail_threshold),
        sides=sides,
    )
