<template>
  <div class="game-view">
    <header class="top-bar">
      <span class="room-name">{{ room.room.value?.name ?? '...' }}</span>
      <span class="turn-info" v-if="room.room.value">
        大回合 {{ room.room.value.big_turn }} · 子回合 {{ room.room.value.sub_turn }}
      </span>
      <button v-if="room.room.value && !room.room.value.current_actor && self.isHost"
              @click="startGame">开始游戏</button>
    </header>

    <div class="main">
      <aside class="left-panel">
        <PlayerList />
        <TurnOrder />
        <DiceRoller />
        <ValueEditor />
        <StatePanel />
      </aside>

      <section class="board-area">
        <DMConsole v-if="self.isHost" ref="dmRef" />
        <div class="canvas-wrap">
          <GameCanvas v-if="room.room.value"
                      :room="room.room.value"
                      :self-token-id="selfTokenId"
                      :visible-cells="visibleCells"
                      :terrain-brush="dmRef?.selected"
                      @path-committed="onPath" />
        </div>
      </section>

      <aside class="right-panel">
        <ChatPanel />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useRoomStore } from '../stores/room'
import { useSelfStore } from '../stores/self'
import { useChatStore } from '../stores/chat'
import { WSClient, type ServerMessage } from '../api/ws'
import GameCanvas from '../components/board/GameCanvas.vue'
import PlayerList from '../components/sidebar/PlayerList.vue'
import TurnOrder from '../components/sidebar/TurnOrder.vue'
import DiceRoller from '../components/sidebar/DiceRoller.vue'
import ValueEditor from '../components/sidebar/ValueEditor.vue'
import StatePanel from '../components/sidebar/StatePanel.vue'
import ChatPanel from '../components/chat/ChatPanel.vue'
import DMConsole from '../components/layout/DMConsole.vue'

const route = useRoute()
const room = useRoomStore()
const self = useSelfStore()
const chat = useChatStore()
const dmRef = ref<InstanceType<typeof DMConsole> | null>(null)

const ws = new WSClient()
let wsSendHandler: ((e: Event) => void) | null = null

const selfTokenId = computed(() => {
  const pid = self.playerId
  return room.room.value?.players[pid]?.token_id
})

/**
 * 计算当前玩家可见格子集合。
 * MVP 阶段：地图数据尚未随 state_sync 下发，
 *  - 团长：上帝视角（返回 undefined = 全可见）
 *  - 玩家：以自身位置为中心的切比雪夫半径圆形
 * 后续 V1 版本接入真实 vision_service 后替换为扇形+射线遮挡。
 */
const visibleCells = computed<Set<string> | undefined>(() => {
  const r = room.room.value
  if (!r) return undefined
  if (self.isHost) return undefined
  const tid = selfTokenId.value
  if (!tid) return new Set<string>()
  const me = r.tokens[tid]
  if (!me?.position) return new Set<string>()
  const range = me.vision_range || r.config.vision_range
  const cells = new Set<string>()
  for (let dy = -range; dy <= range; dy++) {
    for (let dx = -range; dx <= range; dx++) {
      if (Math.max(Math.abs(dx), Math.abs(dy)) > range) continue
      cells.add(`${me.position.x + dx},${me.position.y + dy}`)
    }
  }
  return cells
})

function onPath(path: [number, number][]) {
  if (!selfTokenId.value) return
  ws.send({ type: 'move', payload: { token_id: selfTokenId.value, path } })
}

function startGame() {
  const order = Object.values(room.room.value?.tokens ?? {})
    .filter((t) => !t.is_dead)
    .map((t) => t.id)
  ws.send({ type: 'set_turn_order', payload: { order } })
  ws.send({ type: 'start_game', payload: {} })
}

function dispatchMessage(msg: ServerMessage) {
  if (msg.type === 'state_sync') {
    room.setState(msg.payload)
  } else if (msg.type === 'chat') {
    chat.addMessage(msg.payload)
  } else if (msg.type === 'dice_result') {
    window.dispatchEvent(new CustomEvent('ws-dice-result', { detail: msg.payload }))
  } else if (msg.type === 'error') {
    console.warn('[server error]', msg.payload.message)
  }
}

onMounted(() => {
  const roomId = String(route.params.roomId)
  const pid = self.playerId || crypto.randomUUID()
  const nick = self.nickname || `玩家${pid.slice(0, 4)}`
  self.init(pid, nick)

  wsSendHandler = (e: Event) => {
    const detail = (e as CustomEvent).detail
    ws.send(detail)
  }
  window.addEventListener('ws-send', wsSendHandler)

  ws.onMessage(dispatchMessage)
  ws.connect(roomId, pid, nick)
})

onUnmounted(() => {
  if (wsSendHandler) window.removeEventListener('ws-send', wsSendHandler)
  ws.close()
})
</script>

<style scoped>
.game-view { display: flex; flex-direction: column; height: 100vh; overflow: hidden; font-family: sans-serif; }
.top-bar { display: flex; align-items: center; gap: 16px; padding: 8px 12px; background: #222; color: #eee; }
.top-bar .room-name { font-weight: bold; }
.main { display: grid; grid-template-columns: 240px 1fr 320px; flex: 1; min-height: 0; }
.left-panel { overflow-y: auto; padding: 8px; background: #fafafa; border-right: 1px solid #ccc; }
.board-area { display: flex; flex-direction: column; min-width: 0; }
.canvas-wrap { flex: 1; overflow: auto; padding: 8px; background: #eee; }
.right-panel { border-left: 1px solid #ccc; min-height: 0; }
button { padding: 4px 10px; cursor: pointer; }

/* 移动端兼容：窄屏改为单列堆叠 */
@media (max-width: 900px) {
  .main { grid-template-columns: 1fr; grid-template-rows: auto 1fr auto; }
  .left-panel { max-height: 200px; }
  .right-panel { height: 240px; }
}
</style>
