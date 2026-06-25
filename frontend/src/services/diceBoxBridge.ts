import { ref } from 'vue'

// ============================================================================
// 服务端权威骰子（Option B / 仿 FVTT Dice So Nice）
// ----------------------------------------------------------------------------
// 后端 dice_service 摇骰并返回每颗骰子的真实点数；前端只负责把这串"预定结果"
// 用 3D 物理动画演出来——dice-box-threejs 支持 `2d20@14,7` 这种预定记号，骰子
// 最终会停在指定的面上。因此"骰子停的面"永远等于"服务端算出的值"，根本不存在
// 显示≠结果的可能（旧库 @3d-dice/dice-box 反过来：让物理结果当真值，所以会因
// colliderFaceMap 错配出现 4 显示成 1 的问题）。
// ============================================================================

export interface DieValue { sides: number; value: number }

// dice-box-threejs 自带模型的骰子面数。其它面数（自定义表达式里的 d7、或 d100
// 这种百分骰）不做 3D 演出，仅在历史里展示数字——结果仍然是服务端权威的。
const ANIMATABLE_SIDES = new Set([2, 4, 6, 8, 10, 12, 20])

export function canAnimate(dice: DieValue[]): boolean {
  return dice.length > 0 && dice.every((d) => ANIMATABLE_SIDES.has(d.sides))
}

/**
 * 把一串 (面数, 点数) 拼成 dice-box-threejs 的预定结果记号。
 * 例：[{20,14},{20,7},{6,3}] => "2d20+1d6@14,7,3"
 *
 * `@` 之后是一条拍平的结果列表，按"库内部去重后的骰子生成顺序"逐一对应
 * （已核对库的 parseNotation：相同 op+type 的 set 会被合并）。所以这里必须先
 * 按面数归并（保持首次出现顺序），否则交错的同型骰子会导致结果错位。
 */
export function buildNotation(dice: DieValue[]): string {
  const order: number[] = []
  const bySides = new Map<number, number[]>()
  for (const d of dice) {
    if (!bySides.has(d.sides)) { bySides.set(d.sides, []); order.push(d.sides) }
    bySides.get(d.sides)!.push(d.value)
  }
  const dicePart = order.map((s) => `${bySides.get(s)!.length}d${s}`).join('+')
  const values = order.flatMap((s) => bySides.get(s)!).join(',')
  return `${dicePart}@${values}`
}

// ---------------------------------------------------------------------------
// 主题：dice-box-threejs 用 colorset(颜色) + material(材质) 描述外观。
// 材质是程序化的（plastic/metal/glass/wood/none），texture 用 'none' 不加载任何
// 贴图文件——所以整套骰子零静态资源依赖。
// ---------------------------------------------------------------------------
export const AVAILABLE_THEMES = [
  { id: 'sapphire', label: '蓝金' },
  { id: 'classic',  label: '经典' },
  { id: 'gold',     label: '黄金' },
  { id: 'jade',     label: '翡翠' },
  { id: 'ruby',     label: '红玉' },
] as const

export const currentTheme = ref<string>('sapphire')

interface Preset { foreground: string; background: string; outline: string; material: string }
const PRESETS: Record<string, Preset> = {
  sapphire: { foreground: '#ffd86b', background: '#123a8f', outline: '#0a1f4d', material: 'metal' },
  classic:  { foreground: '#1a1a2e', background: '#f4f4f8', outline: '#1a1a2e', material: 'plastic' },
  gold:     { foreground: '#2b2000', background: '#e6b422', outline: '#7a5b00', material: 'metal' },
  jade:     { foreground: '#eafff0', background: '#1f7a4d', outline: '#0c3d26', material: 'glass' },
  ruby:     { foreground: '#fff0f0', background: '#9c1b2e', outline: '#4d0b15', material: 'glass' },
}

let csCounter = 0
function colorsetFor(themeId: string) {
  const p = PRESETS[themeId] || PRESETS.classic
  // 用唯一 name 绕过库内部 colorset 缓存：库的 'none' 贴图对象是模块级共享的，
  // 缓存命中会导致 material 串台。每次给新名字 → 每次重新套用本主题的材质。
  return {
    name: `da-${themeId}-${csCounter++}`,
    foreground: p.foreground,
    background: p.background,
    outline: p.outline,
    edge: p.background,
    texture: 'none',
    material: p.material,
  }
}

// ---------------------------------------------------------------------------
// 引擎生命周期：dice-box-threejs 基于 three.js + cannon-es（纯 JS 物理，无 wasm）。
// 动态 import，只在第一次真正摇骰时才拉取引擎，不拖累登录页/无骰会话。
// ---------------------------------------------------------------------------
let box: any = null
let initPromise: Promise<void> | null = null

export function ensureDiceBox(containerSelector: string): Promise<void> {
  if (!initPromise) {
    initPromise = import('@3d-dice/dice-box-threejs').then(({ default: DiceBox }) => {
      box = new DiceBox(containerSelector, {
        // assetPath 实际不会触发任何请求：material 程序化、texture='none'、sounds=false
        assetPath: '/assets/dice-box-threejs/',
        theme_customColorset: colorsetFor(currentTheme.value),
        theme_surface: 'green-felt',
        sounds: false,
        // 性能：关闭实时阴影（每帧渲染 shadow map，是低端机卡顿的最大来源）。
        // 金属/玻璃材质本身有反光，关掉阴影后立体感损失不大、帧率明显更稳。
        shadows: false,
        light_intensity: 1.05,
        gravity_multiplier: 500,  // 重力大一点 → 骰子更快落定，缩短动画时长
        baseScale: 100,
        strength: 1.6,
      })
      return box.initialize()
    })
  }
  return initPromise
}

/** 运行时切主题（热更新，下一次摇骰生效，无需重建引擎） */
export async function setTheme(themeId: string): Promise<void> {
  currentTheme.value = themeId
  if (box) await box.updateConfig({ theme_customColorset: colorsetFor(themeId) })
}

/** 用预定结果记号播放一次 3D 动画，骰子停下后 resolve */
export async function animateRoll(notation: string): Promise<void> {
  if (!box) throw new Error('dice box 尚未初始化')
  box.clearDice()
  await box.roll(notation)
}

// ---------------------------------------------------------------------------
// 待演出请求：DiceBoxOverlay.vue 监听这个 ref 来驱动展示。
// 调用方（DiceRoller）拿到服务端权威结果后，把每颗骰子的 (面数,点数) 丢进来；
// overlay 自行判断：标准骰子走 3D 物理动画，没有 3D 模型的骰子（d100/d7/d5/d3…）
// 走 2D 数字揭示，保证任何一掷都有视觉反馈，不会"投不出来"。
// ---------------------------------------------------------------------------
export interface PendingRoll { dice: DieValue[]; resolve: () => void; reject: (e: unknown) => void }
export const pendingRoll = ref<PendingRoll | null>(null)

export function playAnimation(dice: DieValue[]): Promise<void> {
  return new Promise((resolve, reject) => {
    if (dice.length === 0) { resolve(); return }
    pendingRoll.value = { dice, resolve, reject }
  })
}
