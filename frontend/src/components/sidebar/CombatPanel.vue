<template>
  <div class="combat-panel">
    <h3>战斗</h3>

    <!-- 行动按钮 -->
    <div v-if="selfToken && !selfToken.is_dead && isMyTurn" class="actions">
      <button
        class="btn attack"
        :class="{ active: mode === 'attack' }"
        :disabled="selfToken.ap < 1"
        @click="toggleAttack"
      >
        攻击
      </button>
      <button
        class="btn defend"
        :disabled="selfToken.ap < (room?.config?.defend_ap_cost ?? 1)"
        @click="doDefend"
      >
        防御 ({{ room?.config?.defend_ap_cost ?? 1 }}AP)
      </button>
      <button
        class="btn sprint"
        :disabled="selfToken.ap < (room?.config?.sprint_ap_cost ?? 2)"
        @click="toggleSprint"
      >
        疾跑 ({{ room?.config?.sprint_ap_cost ?? 2 }}AP)
      </button>
      <div class="item-row" v-if="usableItems.length">
        <select v-model="selectedItem" class="item-select">
          <option value="">使用道具</option>
          <option v-for="item in usableItems" :key="item" :value="item">
            {{ item }} {{ itemCharges(item) }}
          </option>
        </select>
        <button class="btn use" :disabled="!selectedItem || itemCharges(selectedItem) === '×0'" @click="doUseItem">使用</button>
      </div>
      <button class="btn end-turn" @click="doEndTurn">结束回合</button>
    </div>

    <div v-else-if="selfToken?.is_dead" class="hint dead">你已阵亡</div>
    <div v-else-if="!isMyTurn" class="hint wait">等待回合…</div>
    <div v-else class="hint">未落子</div>

    <!-- 目标提示 -->
    <div v-if="mode === 'attack'" class="mode-hint">
      点击敌方棋子进行攻击（消耗1AP）
      <button class="cancel" @click="mode = null">取消</button>
    </div>
    <div v-if="mode === 'sprint'" class="mode-hint">
      在棋盘上拖动路径疾跑（最多{{ room?.config?.sprint_distance ?? 4 }}格）
      <button class="cancel" @click="mode = null">取消</button>
    </div>

    <!-- 最近战斗日志 -->
    <div class="log" ref="logRef">
      <div
        v-for="(entry, i) in recentLogs"
        :key="i"
        class="log-entry"
        :class="entry.action"
      >
        <div class="header">
          <span class="actor">{{ nameOf(entry.actor_id) }}</span>
          <span class="action">{{ actionLabel(entry.action) }}</span>
          <span v-if="entry.target_id" class="target">→ {{ nameOf(entry.target_id) }}</span>
        </div>
        <div class="effects">
          <div v-for="(r, ri) in entry.results" :key="ri" class="result">
            <span class="rule">{{ r.rule }}</span>
            <div v-for="(e, ei) in r.effects" :key="ei" class="effect">
              <span v-if="e.hit" :class="{ hit: e.hit.is_hit, miss: !e.hit.is_hit }">
                命中判定 D20={{ e.hit.roll }}+{{ e.hit.bonus }}={{ e.hit.total }} vs DC{{ e.hit.dc }}
                {{ e.hit.is_crit ? '暴击!' : e.hit.is_hit ? '命中' : '未命中' }}
              </span>
              <span v-if="e.damage">
                伤害 {{ e.damage.raw_damage }} - 护甲{{ e.damage.armor }} = 
                <b>{{ e.damage.real_damage }}</b>
              </span>
              <span v-if="e.hp_after !== undefined">HP {{ e.hp_after }}</span>
              <span v-if="e.ap_after !== undefined">AP {{ e.ap_after }}</span>
              <span v-if="e.state_id">状态 {{ e.state_id }}</span>
              <span v-if="e.reason" class="reason">{{ e.reason }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-if="!recentLogs.length" class="empty">暂无战斗记录</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useRoomStore } from '../../stores/room'
import { useSelfStore } from '../../stores/self'
import type { CombatLog } from '../../api/types'

const props = defineProps<{
  wsSend: (msg: any) => void
}>()

const emit = defineEmits<{
  (e: 'set-mode', mode: 'attack' | 'sprint' | null): void
  (e: 'attack-target', id: string): void
}>()

const roomStore = useRoomStore()
const self = useSelfStore()

const room = computed(() => roomStore.room)

const mode = ref<'attack' | 'sprint' | null>(null)
const selectedItem = ref('')
const logs = ref<CombatLog[]>([])
const logRef = ref<HTMLElement>()

const selfToken = computed(() => {
  const pid = self.playerId
  const tid = room.value?.players[pid]?.token_id
  return tid ? room.value?.tokens[tid] : null
})

const isMyTurn = computed(() => {
  // current_actor 是 token_id，不是 player_id —— 之前拿 playerId 直接比较，
  // 永远不可能相等，导致回合制下整个攻击/防御/疾跑/结束回合面板永远不出现。
  return !!selfToken.value && room.value?.current_actor === selfToken.value.id
})

const usableItems = computed(() => {
  return selfToken.value?.backpack.filter(i => i && !i.startsWith('空')) || []
})

const recentLogs = computed(() => {
  // 保留最近20条
  return logs.value.slice(-20)
})

function nameOf(id: string) {
  const t = room.value?.tokens[id]
  if (t?.character_name) return t.character_name
  const p = room.value?.players[id]
  if (p?.nickname) return p.nickname
  return id.slice(0, 6)
}

function actionLabel(a: string) {
  const map: Record<string, string> = {
    attack: '攻击', defend: '防御', sprint: '疾跑',
    use_item: '使用道具', end_turn: '结束回合', poison_circle: '毒圈伤害',
    state_tick: '状态效果', ap_regen: 'AP恢复',
  }
  return map[a] || a
}

function itemCharges(item: string): string {
  const charges = selfToken.value?.item_charges?.[item]
  if (charges === undefined) return ''
  return `×${charges}`
}

function toggleAttack() {
  mode.value = mode.value === 'attack' ? null : 'attack'
  emit('set-mode', mode.value)
}

function toggleSprint() {
  mode.value = mode.value === 'sprint' ? null : 'sprint'
  emit('set-mode', mode.value)
}

function setMode(m: 'attack' | 'sprint' | null) {
  mode.value = m
  emit('set-mode', m)
}

function doDefend() {
  const tid = selfToken.value?.id
  if (!tid) return
  props.wsSend({ type: 'defend', payload: { token_id: tid } })
}

function doUseItem() {
  const tid = selfToken.value?.id
  if (!tid || !selectedItem.value) return
  props.wsSend({ type: 'use_item', payload: { token_id: tid, item_name: selectedItem.value } })
  selectedItem.value = ''
}

function doEndTurn() {
  props.wsSend({ type: 'end_turn', payload: {} })
}

// 接收外部战斗日志
function addLog(log: CombatLog) {
  logs.value.push(log)
  nextTick(() => {
    if (logRef.value) logRef.value.scrollTop = logRef.value.scrollHeight
  })
}

// 攻击目标由父组件通知
function onTargetSelected(targetId: string) {
  if (mode.value !== 'attack') return
  const tid = selfToken.value?.id
  if (!tid) return
  props.wsSend({ type: 'attack', payload: { attacker_id: tid, defender_id: targetId } })
  mode.value = null
  emit('set-mode', null)
}

// 疾跑路径由父组件通知
function onSprintPath(path: [number, number][]) {
  if (mode.value !== 'sprint') return
  const tid = selfToken.value?.id
  if (!tid) return
  props.wsSend({ type: 'sprint', payload: { token_id: tid, path } })
  mode.value = null
  emit('set-mode', null)
}

defineExpose({ addLog, onTargetSelected, onSprintPath, mode, setMode })
</script>

<style scoped>
.combat-panel { font-size: 12px; }
h3 { margin: 0 0 6px; font-size: 13px; color: #0f3460; border-bottom: 1px solid #eee; padding-bottom: 4px; }
.actions { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.btn { padding: 4px 8px; border: none; border-radius: 3px; cursor: pointer; font-size: 12px; color: #fff; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn.attack { background: #c33; }
.btn.attack.active { background: #a00; box-shadow: 0 0 0 2px #faa; }
.btn.defend { background: #37a; }
.btn.sprint { background: #a70; }
.btn.use { background: #3a7; }
.btn.end-turn { background: #666; }
.item-row { display: flex; gap: 4px; width: 100%; }
.item-select { flex: 1; padding: 3px; font-size: 12px; border: 1px solid #ccc; border-radius: 3px; }
.mode-hint { padding: 4px 6px; background: #fffbe6; border: 1px solid #fa0; border-radius: 3px; font-size: 11px; margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; }
.cancel { padding: 2px 6px; font-size: 11px; border: none; background: #eee; border-radius: 2px; cursor: pointer; }
.hint { color: #999; font-size: 12px; padding: 4px 0; }
.hint.dead { color: #c33; font-weight: bold; }
.log { max-height: 200px; overflow-y: auto; border-top: 1px solid #eee; padding-top: 4px; }
.log-entry { padding: 4px 0; border-bottom: 1px dashed #f0f0f0; }
.log-entry.attack .header { color: #c33; }
.log-entry.defend .header { color: #37a; }
.header { font-weight: 500; font-size: 11px; }
.actor { color: #0f3460; }
.target { color: #666; }
.effects { margin-left: 8px; font-size: 11px; }
.result { margin: 2px 0; }
.rule { color: #888; font-size: 10px; }
.effect { display: flex; flex-wrap: wrap; gap: 4px 8px; }
.effect .hit { color: #3a7; }
.effect .miss { color: #999; }
.effect b { color: #c33; }
.reason { color: #a70; }
.empty { color: #bbb; text-align: center; padding: 12px 0; font-size: 11px; }
</style>
