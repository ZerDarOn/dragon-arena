<template>
  <div class="battle-view">
    <header class="top-bar">
      <span class="room-name">{{ room.room?.name ?? '...' }}</span>
      <span class="turn-info" v-if="room.room">
        大回合 {{ room.room.big_turn }} · 子回合 {{ room.room.sub_turn }}
      </span>
      <button v-if="room.room && !room.room.current_actor && auth.isAdmin"
              @click="startGame">开始游戏</button>
      <button @click="leave">离开战役</button>
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
        <DMConsole v-if="auth.isAdmin" ref="dmRef" />
        <div class="canvas-wrap">
          <GameCanvas v-if="room.room"
                      :room="room.room"
                      :self-token-id="selfTokenId"
                      :visible-cells="visibleCells"
                      :terrain-brush="dmRef?.selected"
                      @path-committed="onPath" />
        </div>
      </section>

      <aside class="right-panel">
        <ChatPanel :channels="['hall', 'private', 'campaign_hall', 'spatial', 'war_hall']" />
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRoomStore } from '../stores/room'
import { useSelfStore } from '../stores/self'
import { useChatStore } from '../stores/chat'
import { useAuthStore } from '../stores/auth'
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
const router = useRouter()
const room = useRoomStore()
const self = useSelfStore()
const chat = useChatStore()
const auth = useAuthStore()
const dmRef = ref<InstanceType<typeof DMConsole> | null>(null)

const ws = new WSClient()
let wsSendHandler: ((e: Event) => void) | null = null

const selfTokenId = computed(() => {
  const pid = self.playerId
  return room.room?.players[pid]?.token_id
})

/**
 * Compute visible cells for current player.
 * MVP: host = omniscient; player = chebyshev radius around own token.
 * V1: replace with real vision_service (sector + raycast + fog).
 */
const visibleCells = computed<Set<string> | undefined>(() => {
  const r = room.room
  if (!r) return undefined
  if (auth.isAdmin) return undefined
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
  const order = Object.values(room.room?.tokens ?? {})
    .filter((t) => !t.is_dead)
    .map((t) => t.id)
  ws.send({ type: 'set_turn_order', payload: { order } })
  ws.send({ type: 'start_game', payload: {} })
}

function leave() {
  router.push('/workbench')
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
  if (!auth.token) {
    router.push('/login')
    return
  }

  wsSendHandler = (e: Event) => {
    const detail = (e as CustomEvent).detail
    ws.send(detail)
  }
  window.addEventListener('ws-send', wsSendHandler)

  ws.onMessage(dispatchMessage)
  ws.connect(roomId, auth.token)
})

onUnmounted(() => {
  if (wsSendHandler) window.removeEventListener('ws-send', wsSendHandler)
  ws.close()
})
</script>

<style scoped>
.battle-view { display: flex; flex-direction: column; height: 100vh; overflow: hidden; font-family: sans-serif; }
.top-bar { display: flex; align-items: center; gap: 16px; padding: 8px 12px; background: #222; color: #eee; }
.top-bar .room-name { font-weight: bold; }
.main { display: grid; grid-template-columns: 240px 1fr 320px; flex: 1; min-height: 0; }
.left-panel { overflow-y: auto; padding: 8px; background: #fafafa; border-right: 1px solid #ccc; }
.board-area { display: flex; flex-direction: column; min-width: 0; }
.canvas-wrap { flex: 1; overflow: auto; padding: 8px; background: #eee; }
.right-panel { border-left: 1px solid #ccc; min-height: 0; }
button { padding: 4px 10px; cursor: pointer; }

@media (max-width: 900px) {
  .main { grid-template-columns: 1fr; grid-template-rows: auto 1fr auto; }
  .left-panel { max-height: 200px; }
  .right-panel { height: 240px; }
}
</style>
