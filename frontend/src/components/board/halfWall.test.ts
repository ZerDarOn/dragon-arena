import { describe, it, expect } from 'vitest'
import { computeHalfWallRects, brushColorOf, BRUSH_COLORS } from './halfWall'

describe('computeHalfWallRects', () => {
  it('孤立墙（无邻居）画满格', () => {
    expect(computeHalfWallRects({ left: false, right: false, up: false, down: false }))
      .toEqual([{ x: 0, y: 0, w: 1, h: 1 }])
  })

  it('四周都有邻居画满格', () => {
    expect(computeHalfWallRects({ left: true, right: true, up: true, down: true }))
      .toEqual([{ x: 0, y: 0, w: 1, h: 1 }])
  })

  // —— 单向：墙贴邻居那一侧 ——
  it('仅右有邻居 → 画右半格', () => {
    expect(computeHalfWallRects({ left: false, right: true, up: false, down: false }))
      .toEqual([{ x: 0.5, y: 0, w: 0.5, h: 1 }])
  })

  it('仅左有邻居 → 画左半格', () => {
    expect(computeHalfWallRects({ left: true, right: false, up: false, down: false }))
      .toEqual([{ x: 0, y: 0, w: 0.5, h: 1 }])
  })

  it('仅上有邻居 → 画上半格', () => {
    expect(computeHalfWallRects({ left: false, right: false, up: true, down: false }))
      .toEqual([{ x: 0, y: 0, w: 1, h: 0.5 }])
  })

  it('仅有下邻居 → 画下半格', () => {
    expect(computeHalfWallRects({ left: false, right: false, up: false, down: true }))
      .toEqual([{ x: 0, y: 0.5, w: 1, h: 0.5 }])
  })

  // —— 一字（对侧两邻居）：画一字横/竖 ——
  it('左右都有邻居 → 左右两个半格（拼成完整一字竖墙）', () => {
    const r = computeHalfWallRects({ left: true, right: true, up: false, down: false })
    expect(r).toHaveLength(2)
    expect(r).toContainEqual({ x: 0, y: 0, w: 0.5, h: 1 })
    expect(r).toContainEqual({ x: 0.5, y: 0, w: 0.5, h: 1 })
  })

  it('上下都有邻居 → 上下两个半格', () => {
    const r = computeHalfWallRects({ left: false, right: false, up: true, down: true })
    expect(r).toHaveLength(2)
    expect(r).toContainEqual({ x: 0, y: 0, w: 1, h: 0.5 })
    expect(r).toContainEqual({ x: 0, y: 0.5, w: 1, h: 0.5 })
  })

  // —— L 拐角（相邻两方向）：两个半格成 L 形 ——
  it('左+上邻居 → L 形（左半格 + 上半格）', () => {
    const r = computeHalfWallRects({ left: true, right: false, up: true, down: false })
    expect(r).toHaveLength(2)
    expect(r).toContainEqual({ x: 0, y: 0, w: 0.5, h: 1 })
    expect(r).toContainEqual({ x: 0, y: 0, w: 1, h: 0.5 })
  })
})

describe('brushColorOf', () => {
  it('环境画笔 dark 有深色语义（不是 fallback 橙）', () => {
    const c = brushColorOf('dark')
    expect(c).toBeTruthy()
    expect(c!.stroke).not.toBe('#fa0')
  })

  it('环境画笔 light / smoke / clear_meta 各自颜色不同', () => {
    const strokes = ['light', 'smoke', 'clear_meta'].map(b => brushColorOf(b)!.stroke)
    expect(new Set(strokes).size).toBe(3)  // 三者颜色互不相同
  })

  it('所有环境画笔都有显式颜色（不走 fallback）', () => {
    for (const b of ['dark', 'light', 'smoke', 'clear_meta']) {
      expect(BRUSH_COLORS[b]).toBeDefined()
      expect(BRUSH_COLORS[b].stroke).not.toBe('#fa0')  // 不应该是 fallback 橙
    }
  })

  it('undefined / null 笔刷返回 null（无 hover 指示）', () => {
    expect(brushColorOf(undefined)).toBeNull()
    expect(brushColorOf(null)).toBeNull()
    expect(brushColorOf('')).toBeNull()
  })
})
