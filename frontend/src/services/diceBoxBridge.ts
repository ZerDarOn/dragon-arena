import { ref } from 'vue'
import type DiceBox from '@3d-dice/dice-box'
import type { DiceGroupSpec } from './diceExpr'

export interface DiceBoxRequest {
  groups: DiceGroupSpec[]
  resolve: (values: number[]) => void
  reject: (err: unknown) => void
}

// 全局唯一的"待处理摇骰请求"，DiceBoxOverlay.vue 监听这个 ref 来驱动 3D 动画。
// 用一个简单的 ref 而不是事件总线库，足够这一个场景用了。
export const pendingRequest = ref<DiceBoxRequest | null>(null)

/**
 * 请求本地物理摇骰，返回每颗骰子摇出来的真实点数（按 groups 顺序拼平）。
 * 调用方负责把这串点数发给后端，后端只校验+套用规则，不再重新随机一次——
 * 因为 dice-box 这类物理引擎库不支持"强制摇出指定点数"，与其试图让物理结果
 * 凑后端预算好的数字，不如反过来，让真实摇出来的物理结果说话。
 */
export function requestPhysicalRoll(groups: DiceGroupSpec[]): Promise<number[]> {
  return new Promise((resolve, reject) => {
    if (groups.length === 0) { resolve([]); return }
    pendingRequest.value = { groups, resolve, reject }
  })
}

let box: DiceBox | null = null
let initPromise: Promise<void> | null = null

// 动态 import：dice-box 自带的 3D 引擎+物理 worker 体积不小，
// 不应该让登录页/没用到骰子的会话也背上这个加载成本，只在真正第一次摇骰时才拉取。
export function ensureDiceBox(containerSelector: string): Promise<void> {
  if (!initPromise) {
    initPromise = import('@3d-dice/dice-box').then(({ default: DiceBoxCtor }) => {
      box = new DiceBoxCtor(containerSelector, { assetPath: '/assets/dice-box/' })
      return box.init()
    })
  }
  return initPromise
}

export async function rollGroupsPhysically(groups: DiceGroupSpec[]): Promise<number[]> {
  if (!box) throw new Error('dice box 尚未初始化')
  const notation = groups.map((g) => ({ qty: g.count, sides: g.sides }))
  const resultGroups = await box.roll(notation)
  return resultGroups
    .slice()
    .sort((a, b) => a.groupId - b.groupId)
    .flatMap((g) => g.rolls.map((r) => r.value))
}

export function clearDiceBox() { box?.clear() }
