/**
 * 半格视觉墙矩形计算（§8）
 *
 * 视觉原则：墙体矩形贴着「有同类墙邻居」的那一侧绘制。
 * 例如：邻居在右侧 → 墙画右半格；邻居在下方 → 墙画下半格。
 *
 * 返回值是相对格子左上角 (0,0) 的归一化矩形数组（坐标 0~1），
 * 调用方负责乘以 CELL 再加上 px=x*CELL, py=y*CELL 的平移。
 */

export interface NeighborFlags {
  left: boolean
  right: boolean
  up: boolean
  down: boolean
}

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

const HALF = 0.5

/**
 * 根据四方向邻居真值，返回墙体应绘制的矩形列表（归一化坐标，0~1）。
 * 原则：墙体贴着「有同类邻居」的那一侧。
 *  - 无邻居 / 四邻全有：满格
 *  - 否则：每个为 true 的方向贡献一个贴该侧的半格（多向自动形成一字/L 形）
 */
export function computeHalfWallRects(n: NeighborFlags): Rect[] {
  const count = (n.left ? 1 : 0) + (n.right ? 1 : 0) + (n.up ? 1 : 0) + (n.down ? 1 : 0)
  if (count === 0 || count === 4) return [{ x: 0, y: 0, w: 1, h: 1 }]

  const rects: Rect[] = []
  if (n.left) rects.push({ x: 0, y: 0, w: HALF, h: 1 })
  if (n.right) rects.push({ x: HALF, y: 0, w: HALF, h: 1 })
  if (n.up) rects.push({ x: 0, y: 0, w: 1, h: HALF })
  if (n.down) rects.push({ x: 0, y: HALF, w: 1, h: HALF })
  return rects
}

/**
 * 画笔颜色映射（填充 / 描边）。
 * 所有环境类画笔（dark/light/smoke/clear_meta）都有明确语义颜色，
 * 不再走 fallback 橙色 —— 这样用户能看出自己在画什么。
 */
export const BRUSH_COLORS: Record<string, { fill: string; stroke: string }> = {
  // 地貌
  flat:       { fill: 'rgba(240,240,240,0.5)', stroke: '#888' },
  grass:      { fill: 'rgba(153,204,153,0.5)', stroke: '#3a3' },
  dirt:       { fill: 'rgba(187,136,136,0.5)', stroke: '#863' },
  stone:      { fill: 'rgba(170,170,170,0.5)', stroke: '#555' },
  sand:       { fill: 'rgba(238,221,85,0.5)',  stroke: '#aa3' },
  wood:       { fill: 'rgba(204,153,102,0.5)', stroke: '#642' },
  ice:        { fill: 'rgba(204,238,255,0.5)', stroke: '#4af' },
  // 障碍
  wall:       { fill: 'rgba(68,68,68,0.5)',    stroke: '#222' },
  door:       { fill: 'rgba(204,153,102,0.5)', stroke: '#642' },
  glass_wall: { fill: 'rgba(100,200,255,0.4)', stroke: '#4af' },
  water_deep: { fill: 'rgba(51,153,204,0.5)',  stroke: '#39c' },
  lava:       { fill: 'rgba(255,102,0,0.5)',   stroke: '#c30' },
  poison:     { fill: 'rgba(153,204,0,0.5)',   stroke: '#9c0' },
  // 环境 —— 各自语义颜色，避免全橙色混淆
  dark:       { fill: 'rgba(20,20,40,0.6)',    stroke: '#88f' },     // 深蓝紫
  light:      { fill: 'rgba(255,240,120,0.55)', stroke: '#fc0' },    // 金黄（区别于 fallback 橙）
  smoke:      { fill: 'rgba(180,180,180,0.5)', stroke: '#aaa' },     // 灰
  clear_meta: { fill: 'rgba(255,255,255,0.45)', stroke: '#0c0' },    // 绿（清除）
}

/** 默认画笔颜色（未命中时的 fallback） */
export const DEFAULT_BRUSH_COLOR = { fill: 'rgba(250,160,0,0.4)', stroke: '#fa0' }

/** 查询画笔颜色（统一入口） */
export function brushColorOf(brush: string | undefined | null) {
  if (!brush) return null
  return BRUSH_COLORS[brush] ?? DEFAULT_BRUSH_COLOR
}
