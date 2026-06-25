/**
 * 战争迷雾探索记忆（纯客户端，不发送至服务端）
 *
 * 三层状态：
 *   - unexplored : 从未见过的格子
 *   - fog        : 见过但当前不在视野内（灰色调记忆）
 *   - visible    : 当前可见
 *
 * 持久化：localStorage per roomId per playerId
 */
import { ref } from 'vue'

const CELL_DELIM = ','
const STORAGE_PREFIX = 'da_fow_'

export function useFogOfWar() {
  const exploredCells = ref<Set<string>>(new Set())

  function cellKey(x: number, y: number): string {
    return `${x}${CELL_DELIM}${y}`
  }

  function load(roomId: string, playerId: string) {
    const key = `${STORAGE_PREFIX}${roomId}_${playerId}`
    try {
      const raw = localStorage.getItem(key)
      if (raw) {
        const arr: string[] = JSON.parse(raw)
        exploredCells.value = new Set(arr)
      } else {
        exploredCells.value = new Set()
      }
    } catch {
      exploredCells.value = new Set()
    }
  }

  function persist(roomId: string, playerId: string) {
    const key = `${STORAGE_PREFIX}${roomId}_${playerId}`
    try {
      const arr = Array.from(exploredCells.value)
      localStorage.setItem(key, JSON.stringify(arr))
    } catch (e) {
      console.warn('[FogOfWar] failed to persist explored cells:', e)
    }
  }

  /** 每次 state_sync 后调用，标记刚可见的格子为已探索 */
  function markExplored(visibleCells: Set<string>) {
    let changed = false
    for (const k of visibleCells) {
      if (!exploredCells.value.has(k)) {
        exploredCells.value.add(k)
        changed = true
      }
    }
    return changed
  }

  function isExplored(x: number, y: number): boolean {
    return exploredCells.value.has(cellKey(x, y))
  }

  function clear() {
    exploredCells.value = new Set()
  }

  return { exploredCells, load, persist, markExplored, isExplored, clear, cellKey }
}
