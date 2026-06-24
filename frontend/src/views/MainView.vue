<template>
  <div class="main-view">
    <header class="top-bar">
      <span class="welcome">🐉 龙王争霸赛
        <span class="tag" :class="{ admin: auth.isAdmin }">{{ auth.isAdmin ? '管理员' : '玩家' }}</span>
      </span>
      <div class="actions">
        <button @click="showSheet = true">角色卡</button>
        <template v-if="!inBattle">
          <button v-if="auth.isAdmin" @click="showCreate = true">创建战役</button>
          <button @click="showJoin = true">加入战役</button>
        </template>
        <template v-else>
          <button @click="leaveBattle">返回大厅</button>
        </template>
        <button v-if="auth.isAdmin" @click="showUsers = true">用户管理</button>
        <button v-if="auth.isAdmin" @click="showRes = true">资源管理</button>
        <button @click="onLogout">登出</button>
      </div>
    </header>

    <!-- 资源管理侧边栏（战役态，管理员，左侧） -->
    <aside v-if="inBattle && auth.isAdmin && showResPanel" class="res-panel">
      <MiniResPanel @close="showResPanel = false" />
    </aside>
    <button v-if="inBattle && auth.isAdmin && !showResPanel" class="res-toggle" @click="showResPanel = true">📚</button>

    <!-- 角色卡侧边栏（战役态，右侧） -->
    <aside v-if="inBattle && showSheetPanel" class="sheet-panel">
      <MiniSheetPanel @close="showSheetPanel = false" @edit="onSheetEdit" @create="onSheetCreate" />
    </aside>
    <button v-if="inBattle && !showSheetPanel" class="sheet-toggle" @click="showSheetPanel = true">🎭</button>

    <div class="body">
      <!-- 左侧栏：内容根据状态切换 -->
      <aside class="left-panel">
        <!-- 待机态 -->
        <template v-if="!inBattle">
          <div class="idle-left">
            <h3>大厅玩家</h3>
            <p class="hint">登录即可见，暂无在线列表</p>
          </div>
        </template>
        <!-- 战役态 -->
        <template v-else>
          <PlayerList />
          <TurnOrder />
          <CombatPanel ref="combatRef" :ws-send="wsSend" @set-mode="onCombatMode" @attack-target="onAttackTarget" />
          <DiceRoller />
          <!-- 选中棋子信息卡 -->
          <div v-if="selectedToken" class="token-info-card">
            <div class="tic-header">
              <span class="tic-name">{{ selectedToken.name || selectedToken.character_name || selectedToken.id }}</span>
              <span class="tic-size" title="占格大小">{{ selectedToken.size || 1 }}×{{ selectedToken.size || 1 }}</span>
            </div>
            <div class="tic-stat">
              <span class="lbl">HP</span>
              <div class="bar-bg"><div class="bar-fill hp" :style="{width: (selectedToken.hp||0)/(selectedToken.max_hp||1)*100+'%'}"></div></div>
              <span class="val">{{ selectedToken.hp }}/{{ selectedToken.max_hp }}</span>
            </div>
            <div class="tic-stat">
              <span class="lbl">护甲</span><span class="val mono">{{ selectedToken.armor }}</span>
              <span class="lbl">AP</span><span class="val mono">{{ selectedToken.ap }}/{{ selectedToken.max_ap }}</span>
            </div>
            <div v-if="selectedToken.states?.length" class="tic-states">
              <span v-for="s in selectedToken.states" :key="s.id" class="state-tag">{{ s.name }}<small>{{ s.ttl }}T</small></span>
            </div>
          </div>
          <ValueEditor v-if="selectedToken" :token="selectedToken" />
          <StatePanel v-if="selectedToken" :token="selectedToken" />
        </template>
      </aside>

      <!-- 中央地图区 -->
      <main class="center-panel">
        <!-- 待机态：装饰 -->
        <template v-if="!inBattle">
          <div class="idle-stage">
            <div class="logo">🐲</div>
            <h2>Dragon Arena</h2>
            <p class="tagline" v-if="auth.isAdmin">你是管理员 — 点击「创建战役」开始一场新的游戏</p>
            <p class="tagline" v-else>等待管理员创建战役，或通过「加入战役」进入房间号</p>
          </div>
        </template>
        <!-- 战役态：DMConsole(管理员) + GameCanvas -->
        <template v-else>
          <DMConsole v-if="auth.isAdmin" ref="dmRef"
                     @resize="onMapResize" @fill-area="onFillArea" @set-poison-circle="onSetPoisonCircle" @set-fog-of-war="onSetFogOfWar" @set-turn-order="onSetTurnOrder" @shuffle-turn-order="onShuffleTurn" @force-set-actor="onForceActor" @clear-combat-log="onClearCombatLog" />
          <!-- 底图工具栏（管理员可见） -->
          <div v-if="auth.isAdmin" class="bg-toolbar">
            <label class="bg-btn">
              导入底图
              <input type="file" accept="image/*" @change="onBgUpload" hidden />
            </label>
            <template v-if="bgImageData">
              <label class="bg-opacity">透明度
                <input type="range" min="0" max="1" step="0.1" v-model.number="bgOpacity" />
              </label>
              <button @click="clearBgImage">移除底图</button>
            </template>
          </div>
          <div class="canvas-wrap" :class="{ 'placing-mode': !!selectedCharacter && !selfTokenId }">
            <GameCanvas v-if="room.room"
                        ref="canvasRef"
                        :room="room.room"
                        :self-token-id="selfTokenId"
                        :is-admin="auth.isAdmin"
                        :visible-cells="visibleCells"
                        :detected-tokens="room.room.detected_tokens"
                        :terrain-brush="dmRef?.selected"
                        :light-radius="dmRef?.lightRadius"
                        :bg-image="bgImageData"
                        :bg-opacity="bgOpacity"
                        @path-committed="onPath"
                        @cell-click="onCellClick"
                        @token-selected="onTokenSelected"
                        @token-rotate="onTokenRotate"
                        @token-scale="onTokenSize"
                        :combat-mode="combatMode"
                        @token-dblclick="onTokenDblClick"
                        @spawn-actor="onSpawnActor"
                        @spawn-sheet="onSpawnSheet" />
          </div>
        </template>
      </main>

      <!-- 右侧栏：聊天 -->
      <aside class="right-panel">
        <ChatPanel :channels="chatChannels" />
      </aside>
    </div>

    <!-- 受击反馈遮罩 -->
    <div v-if="damageFlash" class="damage-flash" :class="{ shake: damageShake }"></div>

    <!-- Modals (共用) -->
    <Modal v-if="showCreate" title="创建战役" @close="showCreate = false">
      <label>战役名称</label>
      <input v-model="newRoomName" placeholder="如：第一回合淘汰赛" />
      <label>地图宽度 <code>{{ newMapW }}</code></label>
      <input type="range" v-model.number="newMapW" min="10" max="80" />
      <label>地图高度 <code>{{ newMapH }}</code></label>
      <input type="range" v-model.number="newMapH" min="10" max="80" />
      <button @click="doCreateRoom">创建</button>
      <p v-if="createError" class="err">{{ createError }}</p>
    </Modal>

    <Modal v-if="showJoin" title="加入战役" @close="showJoin = false">
      <input v-model="joinRoomId" placeholder="输入房间号" />
      <button @click="doJoin">进入</button>
      <p v-if="joinError" class="err">{{ joinError }}</p>
      <details>
        <summary>可用房间</summary>
        <ul class="room-list">
          <li v-for="r in rooms" :key="r.id" @click="joinRoomId = r.id">
            <strong>{{ r.name }}</strong>
            <span class="meta">{{ r.id.slice(0,8) }} · {{ Object.keys(r.players).length }}人</span>
          </li>
        </ul>
      </details>
    </Modal>

    <Modal v-if="showSheet" title="我的角色卡" @close="showSheet = false">
      <CharacterSheetEditor />
    </Modal>

    <Modal v-if="showUsers && auth.isAdmin" title="用户管理（管理员）" @close="showUsers = false">
      <AdminUserPanel />
    </Modal>

    <!-- 资源管理弹窗（待机态） -->
    <Modal v-if="showRes && auth.isAdmin" title="资源管理（管理员）" @close="showRes = false">
      <ResourceManager />
    </Modal>

    <Modal v-if="showSheetPicker" title="选择角色卡落子" @close="showSheetPicker = false">
      <div v-if="sheetLoading" class="loading">加载中...</div>
      <ul class="sheet-pick" v-else>
        <li v-for="s in mySheets" :key="s.id" @click="pickSheet(s)">
          <strong>{{ s.name }}</strong>
          <span class="meta">HP{{ s.hp_base }} 甲{{ s.armor_base }} AP{{ s.ap_base }}</span>
          <span class="prof">{{ s.profession }}</span>
        </li>
        <li v-if="!mySheets.length" class="empty">还没有角色卡。请先到「角色卡」创建一张。</li>
      </ul>
    </Modal>

    <!-- 双击棋子查看角色/单位卡（只读） -->
    <Modal v-if="viewingToken" :title="`${viewingToken.name || viewingToken.character_name || viewingToken.id} · 信息`" @close="viewingToken = null">
      <div class="token-view">
        <div class="kv-row">
          <span class="k">类型</span><span class="v">{{ viewingToken.type }}</span>
          <span class="k">HP</span><span class="v">{{ viewingToken.hp }}/{{ viewingToken.max_hp }}</span>
          <span class="k">护甲</span><span class="v">{{ viewingToken.armor }}</span>
          <span class="k">AP</span><span class="v">{{ viewingToken.ap }}/{{ viewingToken.max_ap }}</span>
        </div>
        <div class="kv-row" v-if="viewingToken.gold !== undefined">
          <span class="k">金币</span><span class="v">{{ viewingToken.gold }}</span>
          <span class="k">朝向</span><span class="v">{{ ['N','NE','E','SE','S','SW','W','NW'][viewingToken.facing || 0] }}</span>
        </div>
        <div v-if="viewingToken.equipment_slots?.length" class="section">
          <h4>装备栏</h4>
          <ul class="slots">
            <li v-for="(s, i) in viewingToken.equipment_slots" :key="i">
              <span class="slot-name">{{ (['主武器','副武器','护甲','饰品1','饰品2','饰品3'] as string[])[Number(i)] || `槽${Number(i)+1}` }}</span>
              <span class="slot-val">{{ s || '—' }}</span>
            </li>
          </ul>
        </div>
        <div v-if="viewingToken.skill_slots?.length" class="section">
          <h4>技能</h4>
          <ul class="slots">
            <li v-for="(s, i) in viewingToken.skill_slots" :key="i">
              <span class="slot-name">{{ (['技能1','技能2'] as string[])[Number(i)] || `技能${Number(i)+1}` }}</span>
              <span class="slot-val">{{ s || '—' }}</span>
            </li>
          </ul>
        </div>
        <div v-if="viewingToken.backpack?.length" class="section">
          <h4>背包</h4>
          <ul class="slots">
            <li v-for="(s, i) in viewingToken.backpack" :key="i">
              <span class="slot-name">槽{{ Number(i)+1 }}</span>
              <span class="slot-val">{{ s || '—' }}</span>
            </li>
          </ul>
        </div>
        <div v-if="viewingToken.states?.length" class="section">
          <h4>状态</h4>
          <ul class="slots">
            <li v-for="s in viewingToken.states" :key="s.id">
              <span class="slot-name">{{ s.name }}</span>
              <span class="slot-val">TTL {{ s.ttl }}</span>
            </li>
          </ul>
        </div>
        <p class="readonly-hint">只读视图</p>
      </div>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useRoomStore } from '../stores/room'
import { useSelfStore } from '../stores/self'
import { useChatStore } from '../stores/chat'
import { WSClient, type ServerMessage } from '../api/ws'
import {
  createRoom, listRooms, fetchMe, updateRoomConfig,
  listMyCharacters,
} from '../api/rest'
import type { Room, CharacterSheet } from '../api/types'
import ChatPanel from '../components/chat/ChatPanel.vue'
import DMConsole from '../components/layout/DMConsole.vue'
import GameCanvas from '../components/board/GameCanvas.vue'
import PlayerList from '../components/sidebar/PlayerList.vue'
import TurnOrder from '../components/sidebar/TurnOrder.vue'
import DiceRoller from '../components/sidebar/DiceRoller.vue'
import ValueEditor from '../components/sidebar/ValueEditor.vue'
import StatePanel from '../components/sidebar/StatePanel.vue'
import CombatPanel from '../components/sidebar/CombatPanel.vue'
import Modal from '../components/ui/Modal.vue'
import CharacterSheetEditor from '../components/sheets/CharacterSheetEditor.vue'
import AdminUserPanel from '../components/admin/AdminUserPanel.vue'
import ResourceManager from '../components/admin/ResourceManager.vue'
import MiniResPanel from '../components/admin/MiniResPanel.vue'
import MiniSheetPanel from '../components/sheets/MiniSheetPanel.vue'

const router = useRouter()
const auth = useAuthStore()
const room = useRoomStore()
const self = useSelfStore()
const chat = useChatStore()
const dmRef = ref<InstanceType<typeof DMConsole> | null>(null)
const combatRef = ref<InstanceType<typeof CombatPanel> | null>(null)
const canvasRef = ref<InstanceType<typeof GameCanvas> | null>(null)
const combatMode = ref<'attack' | 'sprint' | null>(null)

// 同步 DMConsole 的 paintMode 到 GameCanvas
watch(() => dmRef.value?.paintMode, (mode) => {
  if (canvasRef.value && mode) {
    canvasRef.value.terrainPaintMode = mode
  }
}, { immediate: true })

// Actor 拖拽到地图生成 Token
function onSpawnActor(payload: { actor_id: string; x: number; y: number }) {
  ws?.send({
    type: 'spawn_token',
    payload: { actor_id: payload.actor_id, x: payload.x, y: payload.y },
  })
}

function onSpawnSheet(payload: { sheet_id: string; x: number; y: number }) {
  ws?.send({
    type: 'place_token',
    payload: {
      token_id: `tok_${payload.sheet_id}`,
      x: payload.x, y: payload.y,
      character: { sheet_id: payload.sheet_id },
    },
  })
}

function wsSend(msg: any) { ws?.send(msg) }

function onCombatMode(mode: 'attack' | 'sprint' | null) {
  combatMode.value = mode
}

function onAttackTarget(targetId: string) {
  combatRef.value?.onTargetSelected(targetId)
}

function onSheetEdit(sheet: any) {
  showSheet.value = true
  // TODO: 传递 sheet 给编辑器
}
function onSheetCreate() {
  showSheet.value = true
}

// --- 战役状态 ---
const inBattle = computed(() => !!room.room)
const chatChannels = computed(() =>
  inBattle.value
    ? ['hall', 'private', 'campaign_hall', 'spatial', 'war_hall']
    : ['hall', 'private']
)

const showResPanel = ref(false)
const showSheetPanel = ref(false)

// --- 弹窗 ---
const showCreate = ref(false); const showJoin = ref(false)
const showSheet = ref(false); const showUsers = ref(false)
const showRes = ref(false); const showSheetPicker = ref(false)
const newRoomName = ref(''); const newMapW = ref(30); const newMapH = ref(30)
const createError = ref(''); const joinError = ref('')
const joinRoomId = ref('')
const rooms = ref<Room[]>([])

// --- 落子流程 ---
const sheetLoading = ref(false)
const mySheets = ref<CharacterSheet[]>([])
const selectedCharacter = ref<CharacterSheet | null>(null)
const selectedToken = ref<any>(null)

// --- WS ---
let ws: WSClient | null = null
let wsSendHandler: ((e: Event) => void) | null = null

const selfTokenId = computed(() => {
  const pid = self.playerId
  return room.room?.players[pid]?.token_id
})

const visibleCells = computed<Set<string> | undefined>(() => {
  const r = room.room
  if (!r) return undefined
  if (auth.isAdmin) return undefined  // 管理员看全图
  // 未落子 / 后端未下发 visible_cells：看全图静态
  const arr = r.visible_cells
  if (!arr || !arr.length) return undefined
  const cells = new Set<string>()
  for (const [x, y] of arr) cells.add(`${x},${y}`)
  return cells
})

// --- 操作 ---
async function refreshRooms() {
  try { rooms.value = await listRooms() } catch {}
}

async function doCreateRoom() {
  createError.value = ''
  if (!newRoomName.value) { createError.value = '请输入战役名'; return }
  try {
    const r = await createRoom(newRoomName.value)
    // 更新地图尺寸
    if (newMapW.value !== 30 || newMapH.value !== 30) {
      try { await updateRoomConfig(r.id, { map_width: newMapW.value, map_height: newMapH.value }) }
      catch {}
    }
    showCreate.value = false
    await connectBattle(r.id)
  } catch (e: any) { createError.value = e.message }
}

async function doJoin() {
  joinError.value = ''
  if (!joinRoomId.value) { joinError.value = '请输入房间号'; return }
  showJoin.value = false
  await connectBattle(joinRoomId.value)
}

async function connectBattle(roomId: string) {
  // 先验证 token
  try { await fetchMe() } catch {
    auth.logout(); router.push('/login'); return
  }
  // 断开旧 WS
  disconnectWs()
  // 创建新 WS 连接
  ws = new WSClient()
  wsSendHandler = (e: Event) => {
    const detail = (e as CustomEvent).detail
    ws?.send(detail)
  }
  window.addEventListener('ws-send', wsSendHandler)
  ws.onMessage(dispatchMessage)
  ws.connect(roomId, auth.token!)
  loadBgForRoom(roomId)
}

function disconnectWs() {
  if (wsSendHandler) { window.removeEventListener('ws-send', wsSendHandler); wsSendHandler = null }
  if (ws) { ws.close(); ws = null }
  room.clear()
}

function leaveBattle() {
  disconnectWs()
  refreshRooms()
}

const damageFlash = ref(false)
const damageShake = ref(false)
let damageTimer: any = null

function triggerDamageFeedback() {
  damageFlash.value = true
  damageShake.value = true
  if (damageTimer) clearTimeout(damageTimer)
  damageTimer = setTimeout(() => {
    damageFlash.value = false
    damageShake.value = false
  }, 600)
}

function dispatchMessage(msg: ServerMessage) {
  const m = msg as any
  if (m.type === 'state_sync') room.setState(m.payload)
  else if (m.type === 'chat') chat.addMessage(m.payload)
  else if (m.type === 'combat_log') {
    combatRef.value?.addLog(m.payload)
    // 检查自己是否受到伤害
    const selfId = selfTokenId.value
    if (selfId && m.payload.target_id === selfId) {
      const hasDamage = m.payload.results.some((r: any) =>
        r.effects.some((e: any) => e.damage && e.damage.real_damage > 0)
      )
      if (hasDamage) triggerDamageFeedback()
    }
  }
  else if (m.type === 'dice_result') {
    window.dispatchEvent(new CustomEvent('ws-dice-result', { detail: m.payload }))
  }
  else if (m.type === 'error') {
    console.warn('[server error]', m.payload?.message)
  }
}

// --- 落子 ---
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

function onCellClick(cell: { x: number; y: number; action?: string }) {
  // 径向菜单动作
  if (cell.action) {
    if (cell.action === 'attack') {
      combatRef.value?.setMode('attack')
      return
    }
    if (cell.action === 'move') {
      // 移动由拖拽处理，这里只是激活选择工具
      return
    }
    if (cell.action === 'item') {
      // TODO: 打开道具面板
      return
    }
  }
  // 攻击模式：点击格子不处理，由 token 选择处理
  if (combatMode.value === 'attack') return
  // 疾跑模式：也不处理格子点击
  if (combatMode.value === 'sprint') return
  // 玩家落子
  if (!selectedCharacter.value || selfTokenId.value) return
  const c = selectedCharacter.value
  ws?.send({
    type: 'place_token',
    payload: {
      token_id: `tok_${auth.user?.id}`,
      x: cell.x, y: cell.y,
      character: {
        name: c.name, gender: c.gender, profession: c.profession, talent: c.talent,
        hp_base: c.hp_base, armor_base: c.armor_base, ap_base: c.ap_base, gold: c.gold,
        backpack: c.backpack, equipment_slots: c.equipment_slots, skill_slots: c.skill_slots,
        darkvision: c.darkvision, vision_range: c.vision_range,
        listen_radius: c.listen_radius, passive_perception: c.passive_perception,
        stealth: c.stealth,
        owner_id: auth.user?.id,
      },
    },
  })
  selectedCharacter.value = null
  showSheetPicker.value = false
}

function onPath(path: [number, number][]) {
  const targetId = selectedToken.value?.id || selfTokenId.value
  if (!targetId) return
  ws?.send({ type: 'move', payload: { token_id: targetId, path } })
}

function onTokenSelected(t: any) {
  // 攻击模式：点击敌方 token 发起攻击
  if (combatMode.value === 'attack') {
    const selfId = selfTokenId.value
    if (t.id !== selfId && !t.is_dead) {
      combatRef.value?.onTargetSelected(t.id)
    }
    return
  }
  selectedToken.value = t
}

function onTokenRotate(tokenId: string, facing: number) {
  ws?.send({ type: 'rotate_token', payload: { token_id: tokenId, facing } })
}

function onTokenSize(tokenId: string, size: number) {
  ws?.send({ type: 'size_token', payload: { token_id: tokenId, size } })
}

const viewingToken = ref<any>(null)
function onTokenDblClick(token: any) {
  viewingToken.value = token
}

// --- 监听未落子时自动弹选角色卡 ---
function checkPlacementNeeded() {
  if (inBattle.value && !selfTokenId.value && !selectedCharacter.value && !showSheetPicker.value) {
    openSheetPicker()
  }
}

function onLogout() {
  disconnectWs()
  auth.logout()
  router.push('/login')
}

// --- DM 工具回调 ---
function onSetPoisonCircle(cfg: { center_x: number; center_y: number; radius: number; enabled: boolean }) {
  ws?.send({ type: 'set_poison_circle', payload: cfg })
}

function onSetFogOfWar(enabled: boolean) {
  ws?.send({ type: 'set_fog_of_war', payload: { enabled } })
}

function onSetTurnOrder(order: string[]) {
  ws?.send({ type: 'set_turn_order', payload: { order } })
}
function onShuffleTurn() {
  ws?.send({ type: 'shuffle_turn_order', payload: {} })
}
function onForceActor(tokenId: string) {
  ws?.send({ type: 'force_set_actor', payload: { token_id: tokenId } })
}
function onClearCombatLog() {
  ws?.send({ type: 'clear_combat_log', payload: {} })
}

function onMapResize(w: number, h: number) {
  ws?.send({ type: 'resize_map', payload: { width: w, height: h } })
}
function onFillArea(area: { x1: number; y1: number; x2: number; y2: number; type: string }) {
  ws?.send({ type: 'fill_terrain', payload: area })
}

// --- 底图导入（本地存储，按 roomId）---
const bgImageData = ref<string>('')
const bgOpacity = ref(0.5)
const BG_OPACITY_KEY = 'da_bg_opacity'

function loadBgForRoom(roomId: string) {
  bgImageData.value = localStorage.getItem(`da_bg_${roomId}`) || ''
  const op = localStorage.getItem(BG_OPACITY_KEY)
  bgOpacity.value = op ? parseFloat(op) : 0.5
}

function onBgUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    bgImageData.value = reader.result as string
    const rid = room.room?.id
    if (rid) {
      try { localStorage.setItem(`da_bg_${rid}`, bgImageData.value) }
      catch (err) { console.warn('底图过大，无法存入 localStorage', err) }
    }
  }
  reader.readAsDataURL(file)
  input.value = ''  // 允许再次选同一文件
}

function clearBgImage() {
  bgImageData.value = ''
  const rid = room.room?.id
  if (rid) localStorage.removeItem(`da_bg_${rid}`)
}

onMounted(async () => {
  try { await fetchMe() } catch { auth.logout(); router.push('/login'); return }
  await refreshRooms()
})

// 监听 room 变化，自动触发落子提示
import { watch } from 'vue'
watch(() => room.room, (r) => {
  if (r) checkPlacementNeeded()
})

// opacity 变化持久化
watch(bgOpacity, (v) => {
  try { localStorage.setItem(BG_OPACITY_KEY, String(v)) } catch {}
})

onUnmounted(() => { disconnectWs() })
</script>

<style scoped>
.main-view { display: flex; flex-direction: column; height: 100vh; font-family: sans-serif; overflow: hidden; }
.top-bar { display: flex; justify-content: space-between; align-items: center;
  padding: 8px 16px; background: #1a1a2e; color: #eee; }
.welcome { font-size: 15px; }
.tag { padding: 2px 6px; border-radius: 3px; font-size: 11px; background: #3a7; color: #fff; margin-left: 6px; }
.tag.admin { background: #fa0; }
.actions { display: flex; gap: 8px; }
.actions button { padding: 6px 12px; background: #444; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; font-size: 13px; }
.actions button:hover { background: #555; }
.body { display: grid; grid-template-columns: 240px 1fr 320px; flex: 1; min-height: 0; }
.left-panel { overflow-y: auto; padding: 8px; background: #fafafa; border-right: 1px solid #ccc; }
.center-panel { display: flex; flex-direction: column; min-width: 0; }
.canvas-wrap { flex: 1; overflow: auto; padding: 8px; background: #eee; }
.canvas-wrap.placing-mode { cursor: crosshair; }
.bg-toolbar { display: flex; align-items: center; gap: 12px;
  padding: 6px 10px; background: #f0f0f0; border-bottom: 1px solid #ccc; font-size: 12px; }
.bg-toolbar .bg-btn { padding: 4px 10px; background: #0f3460; color: #fff;
  border-radius: 3px; cursor: pointer; }
.bg-toolbar .bg-btn:hover { background: #1a4a7a; }
.bg-toolbar .bg-opacity { display: flex; align-items: center; gap: 6px; color: #666; }
.bg-toolbar .bg-opacity input { width: 100px; }
.bg-toolbar button { padding: 4px 10px; background: #c33; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; font-size: 12px; }
.right-panel { border-left: 1px solid #ccc; min-height: 0; }

/* 待机态 */
.idle-left { padding: 8px; }
.idle-left h3 { margin: 0 0 6px; font-size: 13px; color: #0f3460; }
.idle-left .hint { color: #999; font-size: 12px; }
.idle-stage { flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; background: radial-gradient(ellipse, #1a1a2e 0%, #0f0f1a 100%);
  color: #eee; }
.idle-stage .logo { font-size: 120px; animation: float 3s ease-in-out infinite; }
@keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
.idle-stage h2 { margin: 12px 0 4px; font-size: 32px; letter-spacing: 2px; }
.tagline { margin: 0 0 24px; color: #aaa; font-size: 14px; max-width: 360px; text-align: center; }

/* Modal slot */
:deep(.modal-body) input { padding: 6px 8px; border: 1px solid #ccc; border-radius: 3px;
  font-size: 13px; width: 100%; box-sizing: border-box; margin-bottom: 8px; }
:deep(.modal-body) input[type=range] { padding: 0; }
:deep(.modal-body) label { display: block; font-size: 12px; color: #666; margin-bottom: 4px; }
:deep(.modal-body) button { padding: 8px 16px; background: #0f3460; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; font-size: 13px; }
:deep(.modal-body) button:hover { background: #1a4a7a; }
:deep(.modal-body) .err { color: #c33; font-size: 12px; margin: 8px 0; }
:deep(.modal-body .room-list) { list-style: none; padding: 0; }
:deep(.modal-body) details summary { cursor: pointer; color: #888; font-size: 12px; margin-top: 8px; }
:deep(.modal-body) details li { padding: 6px 0; border-bottom: 1px solid #eee; cursor: pointer; font-size: 13px; }
:deep(.modal-body) details .meta { color: #999; font-size: 11px; margin-left: 8px; }
:deep(.modal-body) code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-family: monospace; }
:deep(.modal-body .sheet-pick) { list-style: none; padding: 0; margin: 0; min-width: 320px; }
:deep(.modal-body) .sheet-pick li { padding: 10px; border: 1px solid #eee; border-radius: 4px;
  margin-bottom: 8px; cursor: pointer; }
:deep(.modal-body) .sheet-pick li:hover { background: #f0f8ff; }
:deep(.modal-body) .sheet-pick .meta { color: #666; font-size: 12px; margin-left: 8px; }
:deep(.modal-body) .sheet-pick .prof { color: #0f3460; font-size: 12px; margin-left: 8px; }
:deep(.modal-body) .sheet-pick .empty { color: #999; cursor: default; }
:deep(.modal-body) .loading { padding: 20px; color: #999; text-align: center; }
:deep(.modal-body) .token-view { min-width: 320px; font-size: 13px; }
:deep(.modal-body) .token-view .kv-row { display: flex; flex-wrap: wrap; gap: 4px 12px;
  padding: 6px 0; border-bottom: 1px dashed #eee; }
:deep(.modal-body) .token-view .k { color: #888; min-width: 40px; }
:deep(.modal-body) .token-view .v { color: #0f3460; font-weight: 500; margin-right: 8px; }
:deep(.modal-body) .token-view .section h4 { margin: 10px 0 4px; font-size: 12px; color: #fa0; }
:deep(.modal-body) .token-view .slots { list-style: none; padding: 0; margin: 0; }
:deep(.modal-body) .token-view .slots li { display: flex; justify-content: space-between;
  padding: 3px 0; font-size: 12px; border-bottom: 1px solid #f5f5f5; }
:deep(.modal-body) .token-view .slot-name { color: #666; }
:deep(.modal-body) .token-view .slot-val { color: #333; }
:deep(.modal-body) .token-view .readonly-hint { margin-top: 12px; text-align: center;
  color: #bbb; font-size: 11px; }

.damage-flash { position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  box-shadow: inset 0 0 80px rgba(200, 0, 0, 0.4); opacity: 0; transition: opacity 0.3s; }
.damage-flash.shake { opacity: 1; animation: shake 0.5s ease-in-out; }
@keyframes shake { 0%,100% { transform: translate(0,0); } 20% { transform: translate(-4px,2px); } 40% { transform: translate(4px,-2px); } 60% { transform: translate(-2px,4px); } 80% { transform: translate(2px,-4px); } }
/* 资源库侧边栏 — 收窄到 200px */
.res-panel { position: fixed; left: 0; top: 48px; bottom: 0; width: 200px; background: #f8f9fa; border-right: 1px solid #ddd; z-index: 50; display: flex; flex-direction: column; }
.res-toggle { position: fixed; left: 0; top: 50%; transform: translateY(-50%); z-index: 49; padding: 6px; background: #0f3460; color: #fff; border: none; border-radius: 0 4px 4px 0; cursor: pointer; font-size: 14px; }
/* 角色卡侧边栏 — 收窄到 200px，放右侧 */
.sheet-panel { position: fixed; right: 0; top: 48px; bottom: 0; width: 200px; background: #f8f9fa; border-left: 1px solid #ddd; z-index: 50; display: flex; flex-direction: column; }
.sheet-toggle { position: fixed; right: 0; top: 50%; transform: translateY(-50%); z-index: 49; padding: 6px; background: #3a7; color: #fff; border: none; border-radius: 4px 0 0 4px; cursor: pointer; font-size: 14px; }

/* 选中棋子信息卡 */
.token-info-card { background: #1b1b2f; border: 1px solid #333; border-radius: 6px; padding: 8px; margin-bottom: 8px; color: #ddd; font-size: 12px; }
.token-info-card .tic-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.token-info-card .tic-name { font-weight: 700; color: #fff; font-size: 13px; }
.token-info-card .tic-size { background: #333; color: #aaa; padding: 1px 6px; border-radius: 3px; font-size: 10px; }
.token-info-card .tic-stat { display: flex; align-items: center; gap: 6px; margin: 3px 0; }
.token-info-card .lbl { color: #888; min-width: 28px; font-size: 10px; }
.token-info-card .bar-bg { flex: 1; height: 6px; background: #333; border-radius: 3px; overflow: hidden; }
.token-info-card .bar-fill { height: 100%; border-radius: 3px; }
.token-info-card .bar-fill.hp { background: linear-gradient(90deg, #c33, #fa0, #3a7); }
.token-info-card .val { color: #ccc; font-size: 11px; white-space: nowrap; }
.token-info-card .val.mono { font-family: monospace; }
.token-info-card .tic-states { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px; }
.token-info-card .state-tag { background: rgba(100,50,200,0.5); padding: 1px 4px; border-radius: 2px; font-size: 10px; color: #ccf; }

@media (max-width: 900px) {
  .body { grid-template-columns: 1fr; grid-template-rows: auto 1fr 240px; }
  .left-panel { max-height: 200px; }
  .res-panel { width: 100%; }
  .sheet-panel { width: 100%; right: 0; }
}
</style>
