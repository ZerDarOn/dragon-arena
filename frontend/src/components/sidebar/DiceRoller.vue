<template>
  <div class="dice-roller">
    <h3>投骰</h3>

    <div class="quick-row">
      <button v-for="s in quickSides" :key="s" :disabled="rolling" @click="rollSimple(s)">D{{ s }}</button>
    </div>
    <div class="row">
      <input type="number" v-model.number="modifier" placeholder="修正" class="mod-input" />
      <button class="adv" :disabled="rolling" title="优势：2d20 取较高一个" @click="rollAdvantage">优势</button>
      <button class="dis" :disabled="rolling" title="劣势：2d20 取较低一个" @click="rollDisadvantage">劣势</button>
    </div>
    <div class="row expr-row">
      <input v-model="customExpr" placeholder="自定义表达式，如 4d6kh3 / 2d6+1d4+2"
             :disabled="rolling" @keyup.enter="rollCustom" />
      <button :disabled="rolling" @click="rollCustom">投</button>
    </div>

    <ul class="history">
      <li v-for="r in history" :key="r.key" :class="{ self: r.actor === selfId }">
        <div class="head">
          <span class="who">{{ nameOf(r.actor) }}</span>
          <span class="expr">{{ r.expression }}</span>
          <span v-if="r.crit_success" class="tag crit">大成功!</span>
          <span v-if="r.crit_fail" class="tag fail">大失败!</span>
        </div>
        <div class="dice-breakdown">
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
import { ref, computed } from 'vue'
import { useRoomStore } from '../../stores/room'
import { useSelfStore } from '../../stores/self'
import type { DiceResult } from '../../api/types'
import { parseDiceGroups } from '../../services/diceExpr'
import { requestPhysicalRoll } from '../../services/diceBoxBridge'
import { pushToast } from '../../composables/useToast'

const room = useRoomStore()
const self = useSelfStore()
const selfId = computed(() => self.playerId)

const quickSides = [4, 6, 8, 10, 12, 20, 100]
const modifier = ref(0)
const customExpr = ref('')
const rolling = ref(false)

interface RollEntry extends DiceResult { key: number; actor: string }
const history = ref<RollEntry[]>([])
let nextKey = 1

function nameOf(actorId: string): string {
  if (actorId === selfId.value) return '我'
  return room.room?.players?.[actorId]?.nickname || actorId
}

window.addEventListener('ws-dice-result', (e: any) => {
  const d = e.detail
  history.value.unshift({ key: nextKey++, ...d })
  if (history.value.length > 10) history.value.length = 10
})

async function send(expression: string) {
  if (rolling.value) return
  rolling.value = true
  try {
    // 先让真实的 3D 物理骰子摇一遍，把摇出来的点数当作权威结果发给后端——
    // 后端只校验+套用规则（kh/kl/修正/大成功大失败），不会自己再随机一次。
    const groups = parseDiceGroups(expression)
    let rolls: number[] | undefined
    try {
      rolls = await requestPhysicalRoll(groups)
    } catch {
      pushToast('3D 骰子动画加载失败，已改用普通随机结果', 'warn')
      rolls = undefined
    }
    window.dispatchEvent(new CustomEvent('ws-send', {
      detail: { type: 'dice_roll', payload: { expression, ...(rolls ? { rolls } : {}) } },
    }))
  } finally {
    rolling.value = false
  }
}

function fmtMod(): string {
  return modifier.value ? (modifier.value > 0 ? `+${modifier.value}` : `${modifier.value}`) : ''
}

function rollSimple(sides: number) { send(`1d${sides}${fmtMod()}`) }
function rollAdvantage() { send(`2d20kh1${fmtMod()}`) }
function rollDisadvantage() { send(`2d20kl1${fmtMod()}`) }
function rollCustom() {
  if (!customExpr.value.trim()) return
  send(customExpr.value.trim())
}
</script>
<style scoped>
.dice-roller { font-size: 12px; }
h3 { margin: 0 0 6px; font-size: 13px; color: #0f3460; border-bottom: 1px solid #eee; padding-bottom: 4px; }
.quick-row { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.quick-row button { padding: 3px 7px; font-size: 11px; border: 1px solid #ccc; background: #fff; border-radius: 3px; cursor: pointer; }
.quick-row button:hover { background: #eef; }
.row { display: flex; gap: 4px; margin-bottom: 6px; }
.mod-input { width: 56px; padding: 3px; font-size: 11px; border: 1px solid #ccc; border-radius: 2px; }
.row button { padding: 3px 10px; font-size: 11px; border: none; border-radius: 2px; cursor: pointer; color: #fff; }
.row button.adv { background: #3a7; }
.row button.dis { background: #c33; }
.expr-row input { flex: 1; padding: 4px; font-size: 11px; border: 1px solid #ccc; border-radius: 2px; }
.expr-row button { background: #0f3460; }
.history { list-style: none; padding: 0; margin: 0; max-height: 200px; overflow-y: auto; }
.history li { padding: 4px 0; border-bottom: 1px dashed #eee; }
.history li.self { background: #fffbe6; }
.head { display: flex; gap: 4px; align-items: baseline; flex-wrap: wrap; }
.who { font-weight: bold; color: #0f3460; }
.expr { color: #888; font-size: 10px; }
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
