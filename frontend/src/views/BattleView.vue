<template>
  <div class="battle-view">
    <header class="top-bar">
      <span class="room-name">{{ room.room?.name ?? '...' }}</span>
      <span class="turn-info" v-if="room.room">
        大回合 {{ room.room.big_turn }} · 子回合 {{ room.room.sub_turn }}
      </span>
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
        <div v-if="!selfTokenId && selectedCharacter" class="place-hint">
          已选「{{ selectedCharacter.name }}」— 点击地图空格落子
          <button @click="selectedCharacter = null">取消</button>
        </div>
        <div v-else-if="!selfTokenId" class="place-hint">
          你还没落子。请先到「角色卡」选一张，然后回到这里点击地图落子。
          <button @click="openSheetPicker">选择角色卡</button>
        </div>
        <div class="canvas-wrap" :class="{ 'placing-mode': !!selectedCharacter && !selfTokenId }">
          <GameCanvas v-if="room.room"
                      :room="room.room"
                      :self-token-id="selfTokenId"
                      :visible-cells="visibleCells"
                      :terrain-brush="dmRef?.selected"
                      @path-committed="onPath"
                      @cell-click="onCellClick" />
        </div>
      </section>

      <aside class="right-panel">
        <ChatPanel :channels="['hall', 'private', 'campaign_hall', 'spatial', 'war_hall']" />
      </aside>
    </div>

    <Modal v-if="showSheetPicker" title="选择角色卡落子" @close="showSheetPicker = false">
      <div v-if="sheetLoading" class="loading">加载中...</div>
      <ul v-else class="sheet-pick">
        <li v-for="s in mySheets" :key="s.id" @click="pickSheet(s)">
          <strong>{{ s.name }}</strong>
          <span class="meta">HP{{ s.hp_base }} 甲{{ s.armor_base }} AP{{ s.ap_base }}</span>
          <span class="prof">{{ s.profession }}</span>
        </li>
        <li v-if="!mySheets.length" class="empty">
          还没有角色卡。请到工作台「角色卡」先创建一张。
        </li>
      </ul>
    </Modal>
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
import { fetchMe } from '../api/rest'
import GameCanvas from '../components/board/GameCanvas.vue'
import PlayerList from '../components/sidebar/PlayerList.vue'
import TurnOrder from '../components/sidebar/TurnOrder.vue'
import DiceRoller from '../components/sidebar/DiceRoller.vue'
import ValueEditor from '../components/sidebar/ValueEditor.vue'
import StatePanel from '../components/sidebar/StatePanel.vue'
import ChatPanel from '../components/chat/ChatPanel.vue'
import DMConsole from '../components/layout/DMConsole.vue'
import Modal from '../components/ui/Modal.vue'
import { listMyCharacters } from '../api/rest'
import type { CharacterSheet } from '../api/types'

const route = useRoute()
const router = useRouter()
const room = useRoomStore()
const self = useSelfStore()
const chat = useChatStore()
const auth = useAuthStore()
const dmRef = ref<InstanceType<typeof DMConsole> | null>(null)

const ws = new WSClient()
let wsSendHandler: ((e: Event) => void) | null = null

// Character placement flow
const showSheetPicker = ref(false)
const sheetLoading = ref(false)
const mySheets = ref<CharacterSheet[]>([])
const selectedCharacter = ref<CharacterSheet | null>(null)

async function openSheetPicker() {
  showSheetPicker.value = true
  sheetLoading.value = true
  try { mySheets.value = await listMyCharacters() }
  finally { sheetLoading.value = false }
}

function pickSheet(s: CharacterSheet) {
  selectedCharacter.value = s
  showSheetPicker.value = false
}

function onCellClick(cell: { x: number; y: number }) {
  if (!selectedCharacter.value || selfTokenId.value) return
  const c = selectedCharacter.value
  ws.send({
    type: 'place_token',
    payload: {
      token_id: `tok_${auth.user?.id}`,
      x: cell.x, y: cell.y,
      character: {
        name: c.name, gender: c.gender, profession: c.profession, talent: c.talent,
        hp_base: c.hp_base, armor_base: c.armor_base, ap_base: c.ap_base, gold: c.gold,
        backpack: c.backpack, equipment_slots: c.equipment_slots, skill_slots: c.skill_slots,
        owner_id: auth.user?.id,
      },
    },
  })
  selectedCharacter.value = null
}

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

function leave() {
  router.push('/workbench')
}

function dispatchMessage(msg: ServerMessage) {
  const m = msg as any
  if (m.type === 'state_sync') {
    room.setState(m.payload)
  } else if (m.type === 'chat') {
    chat.addMessage(m.payload)
  } else if (m.type === 'combat_log') {
    // 战斗日志已合并到 MainView，这里忽略
  } else if (m.type === 'dice_result') {
    window.dispatchEvent(new CustomEvent('ws-dice-result', { detail: m.payload }))
  } else if (m.type === 'error') {
    console.warn('[server error]', m.payload?.message)
  }
}

onMounted(async () => {
  // Verify token before connecting WS
  try { await fetchMe() } catch {
    auth.logout()
    router.push('/login')
    return
  }

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
.place-hint { padding: 8px 12px; background: #fff3cd; border-bottom: 1px solid #ffeaa7;
  font-size: 13px; display: flex; align-items: center; gap: 12px; }
.place-hint button { background: #fa0; color: #fff; border: none; padding: 4px 10px;
  border-radius: 3px; cursor: pointer; }
.canvas-wrap.placing-mode { cursor: crosshair; }
.sheet-pick { list-style: none; padding: 0; margin: 0; min-width: 320px; }
.sheet-pick li { padding: 10px; border: 1px solid #eee; border-radius: 4px; margin-bottom: 8px;
  cursor: pointer; }
.sheet-pick li:hover { background: #f0f8ff; }
.sheet-pick .meta { color: #666; font-size: 12px; margin-left: 8px; }
.sheet-pick .prof { color: #0f3460; font-size: 12px; margin-left: 8px; }
.sheet-pick .empty { color: #999; cursor: default; }
.sheet-pick .empty:hover { background: transparent; }
.loading { padding: 20px; color: #999; text-align: center; }

@media (max-width: 900px) {
  .main { grid-template-columns: 1fr; grid-template-rows: auto 1fr auto; }
  .left-panel { max-height: 200px; }
  .right-panel { height: 240px; }
}
</style>
