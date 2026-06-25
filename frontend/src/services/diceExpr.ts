// 跟后端 app/services/dice_service.py 的 _TOKEN_RE 同一套语法（保持两边一致）。
// 这里只负责把表达式拆成"需要物理摇出来的骰子组"（数量+面数），kh/kl/修正这些
// 不影响"摇什么"，留给后端用同一份权威逐字解析来套用规则。
const TOKEN_RE = /([+-])?\s*(?:(\d*)d(\d+)(?:k[hl]\d+)?|(\d+))/gi

export interface DiceGroupSpec { count: number; sides: number }

export function parseDiceGroups(expr: string): DiceGroupSpec[] {
  const cleaned = (expr || '').replace(/\s+/g, '')
  const groups: DiceGroupSpec[] = []
  let m: RegExpExecArray | null
  TOKEN_RE.lastIndex = 0
  while ((m = TOKEN_RE.exec(cleaned))) {
    const [, , countStr, sidesStr] = m
    if (sidesStr) {
      const count = countStr ? parseInt(countStr, 10) : 1
      const sides = parseInt(sidesStr, 10)
      if (count > 0 && sides > 1) groups.push({ count, sides })
    }
  }
  return groups
}
