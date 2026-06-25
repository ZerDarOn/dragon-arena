<template>
  <div class="turn-order">
    <h3>行动顺序</h3>
    <div class="phase" v-if="room.room?.current_actor">
      第 {{ room.room?.big_turn }} 回合 · 子回合 {{ room.room?.sub_turn }}
    </div>
    <div class="phase" v-else>未开始</div>

    <!-- Phase 2: 回合倒计时 -->
    <div class="countdown" v-if="remainingSec !== null && remainingSec >= 0"
         :class="{ urgent: remainingSec <= 3 }">
      ⏱ {{ remainingSec }}s
    </div>

    <ol>
      <li v-for="tid in orderWithNames" :key="tid.id"
          :class="{ active: tid.id === room.room?.current_actor, me: tid.isMe, dead: tid.isDead }">
        <span class="ord">{{ tid.idx + 1 }}</span>
        <span class="name" :class="{ dead: tid.isDead }">{{ tid.label }}</span>
        <span v-if="tid.isMe" class="tag">你</span>
        <span class="score" v-if="tid.score !== undefined">{{ tid.score }}分</span>
      </li>
    </ol>

    <!-- 管理员控制（未开始游戏时） -->
    <div class="controls" v-if="auth.isAdmin && !room.room?.current_actor">
      <button @click="onShuffle">抽签</button>
      <button @click="onStart">开始游戏</button>
    </div>

    <!-- 查看排名 -->
    <button class="ranking-btn" v-if="room.room?.current_actor" @click="showRanking">查看排名</button>

    <!-- 当前行动者 -->
    <button v-if="isCurrentActor" class="end-turn" @click="endTurn">结束我的回合</button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoomStore } from '../../stores/room'
import { useSelfStore } from '../../stores/self'
import { useAuthStore } from '../../stores/auth'

const room = useRoomStore()
const self = useSelfStore()
const auth = useAuthStore()

const orderWithNames = computed(() => {
  const r = room.room
  if (!r) return []
  const selfToken = r.players[self.playerId]?.token_id
  return (r.turn_order || []).map((tid, idx) => {
    const tok = r.tokens[tid]
    const ownerEntry = Object.values(r.players).find((p: any) => p.token_id === tid)
    const label = tok?.character_name || ownerEntry?.nickname || tid
    return {
      id: tid, idx, label,
      isMe: tid === selfToken,
      isDead: tok?.is_dead,
      score: tok?.score,
    }
  })
})

const isCurrentActor = computed(() => {
  const r = room.room
  if (!r) return false
  const myToken = r.players[self.playerId]?.token_id
  return myToken === r.current_actor
})

// Phase 2: 回合倒计时（每秒刷新）
const now = ref(Date.now() / 1000)
let timerId: number | null = null
onMounted(() => { timerId = window.setInterval(() => { now.value = Date.now() / 1000 }, 500) })
onUnmounted(() => { if (timerId) clearInterval(timerId) })

const remainingSec = computed<number | null>(() => {
  const deadline = (room.room as any)?.turn_deadline
  if (!deadline) return null
  return Math.max(0, Math.ceil(deadline - now.value))
})

function showRanking() {
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'get_ranking', payload: {} },
  }))
}

function onShuffle() {
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'shuffle_turn_order', payload: {} },
  }))
}

function onStart() {
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'start_game', payload: {} },
  }))
}

function endTurn() {
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'end_turn', payload: {} },
  }))
}
</script>

<style scoped>
.turn-order { font-size: 12px; }
h3 { margin: 0 0 4px; font-size: 13px; color: #0f3460; border-bottom: 1px solid #eee; padding-bottom: 4px; }
.phase { color: #666; font-size: 11px; margin-bottom: 6px; }
.countdown { font-size: 16px; font-weight: bold; color: #0f3460; text-align: center;
  margin-bottom: 6px; padding: 2px; background: #e8f4ff; border-radius: 3px; }
.countdown.urgent { color: #c00; background: #fee; animation: pulse 1s infinite; }
@keyframes pulse { 50% { opacity: 0.5; } }
ol { list-style: none; padding: 0; margin: 0 0 8px; }
li { display: flex; align-items: center; gap: 6px; padding: 3px 6px; border-radius: 3px; }
li.active { background: #fff3cd; font-weight: bold; }
li.me { border-left: 3px solid #fa0; padding-left: 3px; }
.ord { color: #999; width: 16px; }
.name { flex: 1; }
.tag { background: #fa0; color: #fff; padding: 1px 4px; border-radius: 2px; font-size: 10px; }
.score { font-size: 10px; color: #6a3; }
.controls { display: flex; gap: 6px; margin-bottom: 6px; }
.controls button { flex: 1; padding: 4px; font-size: 11px; border: none; border-radius: 3px; cursor: pointer; }
.controls button:first-child { background: #fa0; color: #fff; }
.controls button:last-child { background: #3a7; color: #fff; }
li.dead { opacity: 0.4; }
.name.dead { text-decoration: line-through; }
.ranking-btn { width: 100%; padding: 4px; margin-bottom: 6px; background: #0f3460; color: #fff;
  border: none; border-radius: 3px; cursor: pointer; font-size: 11px; }
.end-turn { width: 100%; padding: 6px; background: #c33; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; font-size: 12px; }
</style>
