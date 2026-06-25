<template>
  <div class="dice-roller">
    <h3>投骰</h3>

    <!-- 骰子托盘：左键 +1，右键 -1（仿 FVTT 聊天栏骰子托盘） -->
    <div class="dice-tray">
      <div v-for="s in diceTypes" :key="s" class="dice-slot"
           :class="{ active: (counts[s] || 0) > 0 }"
           @click.prevent="addDie(s)" @contextmenu.prevent="removeDie(s)">
        <span class="die-face">D{{ s }}</span>
        <span v-if="counts[s]" class="die-count">{{ counts[s] }}</span>
      </div>
    </div>
    <p class="tray-hint">左键 +1 · 右键 -1</p>

    <!-- d20 优势/劣势切换（只在选了 d20 时出现） -->
    <div v-if="(counts[20] || 0) > 0" class="d20-mode">
      <button :class="{ active: d20Mode === 'normal' }" @click="d20Mode = 'normal'">普通</button>
      <button :class="{ active: d20Mode === 'advantage' }" @click="d20Mode = 'advantage'"
              title="优势：2d20 取较高一个">优势</button>
      <button :class="{ active: d20Mode === 'disadvantage' }" @click="d20Mode = 'disadvantage'"
              title="劣势：2d20 取较低一个">劣势</button>
    </div>

    <!-- 修正值 + 主题 + 暗骰 -->
    <div class="config-row">
      <input type="number" v-model.number="modifier" placeholder="修正" class="mod-input" />
      <select v-model="themeId" @change="onThemeChange" class="theme-select" title="骰子外观主题">
        <option v-for="t in themes" :key="t.id" :value="t.id">{{ t.label }}</option>
      </select>
    </div>

    <div class="vis-row">
      <button :class="{ active: visibility === 'public' }" @click="visibility = 'public'"
              title="所有人都能看到结果">明骰</button>
      <button :class="{ active: visibility === 'gm' }" @click="visibility = 'gm'"
              title="只有 DM 能看到结果">DM暗骰</button>
      <button :class="{ active: visibility === 'self' }" @click="visibility = 'self'"
              title="只有自己和 DM 能看到">自查</button>
    </div>

    <!-- 组合表达式预览 + 投骰 -->
    <div class="expr-row">
      <input v-model="exprPreview" placeholder="点上方骰子组合" readonly class="expr-preview" />
      <button class="roll-btn" :disabled="rolling || !exprPreview"
              @click="rollTray">投骰</button>
    </div>

    <!-- 自定义表达式（高级） -->
    <details class="advanced">
      <summary>自定义表达式</summary>
      <div class="expr-row">
        <input v-model="customExpr" placeholder="如 4d6kh3 / 2d6+1d4+2"
               :disabled="rolling" @keyup.enter="rollCustom" />
        <button :disabled="rolling" @click="rollCustom">投</button>
      </div>
    </details>

    <!-- 投骰历史 -->
    <ul class="history">
      <li v-for="r in history" :key="r.key" :class="{ self: r.actor === selfId, hidden: r.hidden }">
        <div class="head">
          <span class="who">{{ nameOf(r.actor) }}</span>
          <span v-if="r.visibility === 'gm'" class="vis-tag gm">DM暗骰</span>
          <span v-if="r.visibility === 'self'" class="vis-tag self">自查</span>
          <span v-if="r.hidden" class="vis-tag hidden-tag">不可见</span>
          <span v-if="!r.hidden" class="expr">{{ r.expression }}</span>
          <span v-if="!r.hidden && r.crit_success" class="tag crit">大成功!</span>
          <span v-if="!r.hidden && r.crit_fail" class="tag fail">大失败!</span>
        </div>
        <div v-if="!r.hidden" class="dice-breakdown">
          <span v-for="(g, gi) in r.groups" :key="gi" class="group">
            <span v-if="g.sign < 0" class="op">-</span>
            <span v-for="(d, di) in g.rolls" :key="di"
                  class="die" :class="{ dropped: !d.kept, d20: d.sides === 20 }">{{ d.value }}</span>
          </span>
          <span v-if="r.modifier" class="flat-mod">{{ r.modifier > 0 ? '+' : '' }}{{ r.modifier }}</span>
          <span class="eq">= {{ r.total }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { useRoomStore } from '../../stores/room'
import { useSelfStore } from '../../stores/self'
import type { DiceResult } from '../../api/types'
import { playAnimation, currentTheme, AVAILABLE_THEMES, setTheme } from '../../services/diceBoxBridge'

const room = useRoomStore()
const self = useSelfStore()
const selfId = computed(() => self.playerId)

// 骰子托盘状态（d2 = 硬币，dice-box-threejs 原生支持的两面骰）
const diceTypes = [2, 4, 6, 8, 10, 12, 20, 100] as const
const counts = reactive<Record<number, number>>({})
const modifier = ref(0)
const d20Mode = ref<'normal' | 'advantage' | 'disadvantage'>('normal')

// 主题 & 暗骰
const themeId = ref(currentTheme.value)
const themes = AVAILABLE_THEMES
const visibility = ref<'public' | 'gm' | 'self'>('public')

const rolling = ref(false)

// 组合表达式预览（根据托盘状态自动生成）
const exprPreview = computed(() => {
  const parts: string[] = []
  for (const s of diceTypes) {
    const c = counts[s] || 0
    if (c <= 0) continue
    if (s === 20 && d20Mode.value !== 'normal') {
      // 优势/劣势：强制 2d20kh1 / 2d20kl1（不管用户选了几颗 d20，都按 2 颗处理）
      parts.push(d20Mode.value === 'advantage' ? '2d20kh1' : '2d20kl1')
    } else {
      parts.push(`${c}d${s}`)
    }
  }
  // 合并同面数（优势/劣势模式可能和手动加的 d20 冲突，取后者覆盖）
  const expr = parts.join('+')
  if (!expr) return ''
  return modifier.value ? `${expr}${modifier.value > 0 ? '+' : ''}${modifier.value}` : expr
})

function addDie(s: number) {
  counts[s] = (counts[s] || 0) + 1
}
function removeDie(s: number) {
  if (counts[s] && counts[s] > 0) {
    counts[s]--
    if (counts[s] === 0) delete counts[s]
  }
}
function resetTray() {
  for (const k of Object.keys(counts)) delete counts[Number(k)]
  modifier.value = 0
  d20Mode.value = 'normal'
}

async function onThemeChange() {
  await setTheme(themeId.value)
}

// 看门狗：万一服务端没回（表达式非法只回 error、或断线），别让按钮永远卡在 rolling
let rollWatchdog: ReturnType<typeof setTimeout> | null = null

function send(expression: string, vis: 'public' | 'gm' | 'self') {
  if (rolling.value) return
  rolling.value = true
  if (rollWatchdog) clearTimeout(rollWatchdog)
  rollWatchdog = setTimeout(() => { rolling.value = false; rollWatchdog = null }, 8000)
  // 只发表达式，服务端权威摇骰。结果回来后（见下方 ws-dice-result）再用 3D 动画
  // 演到服务端算出的点数——前端不再自己随机。
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'dice_roll', payload: { expression, visibility: vis } },
  }))
}

function rollTray() {
  if (!exprPreview.value) return
  send(exprPreview.value, visibility.value)
  resetTray()
}

const customExpr = ref('')

function rollCustom() {
  if (!customExpr.value.trim()) return
  send(customExpr.value.trim(), visibility.value)
  customExpr.value = ''
}

// ---- 投骰历史 ----
interface RollEntry extends DiceResult { key: number; actor: string }
const history = ref<RollEntry[]>([])
let nextKey = 1

function nameOf(actorId: string): string {
  if (actorId === selfId.value) return '我'
  return room.room?.players?.[actorId]?.nickname || actorId
}

window.addEventListener('ws-dice-result', async (e: any) => {
  const d = e.detail
  const isMine = d.actor === selfId.value
  // 我自己的明结果（带 groups）→ 先用 3D 动画演到服务端算出的点数，演完再入历史，
  // 这样"骰子停的面"和历史里的数字一定一致。别人的、或暗骰模糊结果直接入历史。
  if (isMine && rolling.value && !d.hidden && Array.isArray(d.groups) && d.groups.length) {
    if (rollWatchdog) { clearTimeout(rollWatchdog); rollWatchdog = null }
    const dice = d.groups.flatMap((g: any) =>
      (g.rolls || []).map((r: any) => ({ sides: g.sides, value: r.value })))
    try { await playAnimation(dice) } catch { /* 动画失败不影响结果展示 */ }
    rolling.value = false
  }
  history.value.unshift({ key: nextKey++, ...d })
  if (history.value.length > 15) history.value.length = 15
})
</script>

<style scoped>
.dice-roller { font-size: 12px; }
h3 { margin: 0 0 8px; font-size: 13px; color: #0f3460; border-bottom: 1px solid #eee; padding-bottom: 4px; }

/* 骰子托盘 */
.dice-tray { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 2px; }
.dice-slot {
  position: relative; display: flex; align-items: center; justify-content: center;
  width: 42px; height: 42px; border: 2px solid #ccc; border-radius: 8px;
  background: #fff; cursor: pointer; user-select: none; transition: all 0.15s;
}
.dice-slot:hover { border-color: #0f3460; background: #eef; }
.dice-slot.active { border-color: #0f3460; background: #eef; box-shadow: 0 0 4px rgba(15,52,96,0.3); }
.die-face { font-size: 12px; font-weight: bold; color: #0f3460; }
.die-count {
  position: absolute; top: -6px; right: -6px;
  min-width: 18px; height: 18px; border-radius: 9px;
  background: #c33; color: #fff; font-size: 11px; font-weight: bold;
  display: flex; align-items: center; justify-content: center; padding: 0 4px;
}
.tray-hint { color: #999; font-size: 10px; margin: 2px 0 6px; }

/* d20 优势/劣势 */
.d20-mode { display: flex; gap: 4px; margin-bottom: 6px; }
.d20-mode button {
  flex: 1; padding: 3px 0; font-size: 11px; border: 1px solid #ccc;
  background: #fff; border-radius: 3px; cursor: pointer;
}
.d20-mode button.active { background: #0f3460; color: #fff; border-color: #0f3460; }

/* 配置行 */
.config-row { display: flex; gap: 4px; margin-bottom: 6px; }
.mod-input { width: 60px; padding: 3px; font-size: 11px; border: 1px solid #ccc; border-radius: 3px; }
.theme-select { flex: 1; padding: 3px; font-size: 11px; border: 1px solid #ccc; border-radius: 3px; cursor: pointer; }

/* 暗骰切换 */
.vis-row { display: flex; gap: 4px; margin-bottom: 6px; }
.vis-row button {
  flex: 1; padding: 4px 0; font-size: 10px; border: 1px solid #ccc;
  background: #fff; border-radius: 3px; cursor: pointer; color: #666;
}
.vis-row button.active { background: #2a4a6a; color: #fff; border-color: #2a4a6a; }

/* 表达式预览 + 投骰按钮 */
.expr-row { display: flex; gap: 4px; margin-bottom: 6px; }
.expr-preview { flex: 1; padding: 4px; font-size: 12px; border: 1px solid #0f3460; border-radius: 3px; background: #f8f8ff; color: #0f3460; font-weight: bold; }
.roll-btn { padding: 4px 16px; font-size: 12px; border: none; border-radius: 3px; background: #c33; color: #fff; cursor: pointer; font-weight: bold; }
.roll-btn:disabled { background: #ccc; cursor: not-allowed; }

/* 高级折叠 */
.advanced { margin-bottom: 6px; }
.advanced summary { font-size: 10px; color: #888; cursor: pointer; padding: 2px 0; }
.advanced .expr-row { margin-top: 4px; }
.advanced input { flex: 1; padding: 4px; font-size: 11px; border: 1px solid #ccc; border-radius: 2px; }
.advanced button { padding: 4px 10px; font-size: 11px; border: none; border-radius: 2px; background: #0f3460; color: #fff; cursor: pointer; }

/* 历史 */
.history { list-style: none; padding: 0; margin: 0; max-height: 240px; overflow-y: auto; }
.history li { padding: 4px 0; border-bottom: 1px dashed #eee; }
.history li.self { background: #fffbe6; }
.history li.hidden { opacity: 0.6; font-style: italic; }
.head { display: flex; gap: 4px; align-items: baseline; flex-wrap: wrap; }
.who { font-weight: bold; color: #0f3460; }
.expr { color: #888; font-size: 10px; }
.vis-tag { padding: 0 4px; border-radius: 2px; font-size: 9px; color: #fff; }
.vis-tag.gm { background: #6a0; }
.vis-tag.self { background: #06a; }
.vis-tag.hidden-tag { background: #999; }
.tag { padding: 0 4px; border-radius: 2px; font-size: 10px; color: #fff; }
.tag.crit { background: #3a7; }
.tag.fail { background: #c33; }
.dice-breakdown { display: flex; gap: 3px; align-items: center; flex-wrap: wrap; margin-top: 2px; }
.group { display: flex; gap: 2px; align-items: center; }
.op { color: #888; font-weight: bold; }
.die {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 3px; border-radius: 3px;
  background: #0f3460; color: #fff; font-size: 11px; font-weight: bold;
}
.die.dropped { background: #ccc; color: #888; text-decoration: line-through; }
.die.d20 { background: #fa0; color: #1a1a2e; }
.flat-mod { color: #666; font-size: 11px; }
.eq { font-weight: bold; color: #0f3460; margin-left: 2px; }
</style>
