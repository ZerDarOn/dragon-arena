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
        <button @click="showRes = true">资源库</button>
        <button @click="onLogout">登出</button>
      </div>
    </header>

    <div v-if="inBattle && wsStatus !== 'open'" class="conn-banner">
      {{ wsStatus === 'reconnecting' ? '⚠ 与服务器断开，正在重连…' : '⚠ 正在连接服务器…' }}
    </div>

    <!-- 资源库侧边栏（战役态，全员可读，左侧）—— 与导航「资源库」共用同一个 ResourceManager；
         写操作/拖拽落子按权限锁（usePermission）。不再维护单独的 MiniResPanel。 -->
    <aside v-if="inBattle && showResPanel" class="res-panel">
      <div class="res-panel-head">
        <span>📚 资源库</span>
        <button class="res-close" @click="showResPanel = false">×</button>
      </div>
      <div class="res-panel-body"><ResourceManager :in-battle="inBattle" @edit-sheet="onSheetEdit" @create-sheet="onSheetCreate" /></div>
    </aside>
    <button v-if="inBattle && !showResPanel" class="res-toggle" @click="showResPanel = true">📚</button>


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
                     @resize="onMapResize" @fill-area="onFillArea" @set-poison-circle="onSetPoisonCircle" @set-fog-of-war="onSetFogOfWar" @set-player-placement="onSetPlayerPlacement" @set-free-mode="onSetFreeMode" @random-placement="onRandomPlacement" @bg-transform="onBgTransform" @set-turn-order="onSetTurnOrder" @shuffle-turn-order="onShuffleTurn" @force-set-actor="onForceActor" @clear-combat-log="onClearCombatLog" />
          <!-- 底图工具栏（管理员可见） -->
          <div v-if="auth.isAdmin" class="bg-toolbar">
            <label class="bg-btn">
              {{ bgUploading ? '上传中...' : '导入底图' }}
              <input type="file" accept="image/*" @change="onBgUpload" hidden :disabled="bgUploading" />
            </label>
            <template v-if="room.room?.bg_image">
              <label class="bg-opacity">透明度
                <input type="range" min="0" max="1" step="0.1"
                       :value="room.room?.bg_opacity ?? 0.5"
                       @change="onBgOpacityInput" />
              </label>
              <button @click="clearBgImage">移除底图</button>
            </template>
          </div>
          <!-- 攻击多选目标条 -->
          <div v-if="combatMode === 'attack'" class="attack-bar">
            <span class="ab-hint">点敌人选目标（可多选）</span>
            <label class="ab-mod">修正 <input type="number" v-model.number="attackModifier" /></label>
            <select v-model="attackAdv" class="ab-adv" title="优势=2D20取高，劣势=取低">
              <option value="normal">普通</option>
              <option value="adv">优势</option>
              <option value="dis">劣势</option>
            </select>
            <span class="ab-count">已选 {{ attackTargets.length }}</span>
            <button class="ab-confirm" :disabled="!attackTargets.length" @click="confirmAttack">
              🎲 攻击选中目标
            </button>
            <button class="ab-cancel" @click="cancelAttack">取消</button>
          </div>
          <div class="canvas-wrap" :class="{ 'placing-mode': !!selectedCharacter && !selfTokenId }">
            <GameCanvas v-if="room.room"
                        ref="canvasRef"
                        :room="room.room"
                        :self-token-id="selfTokenId"
                        :is-admin="auth.isAdmin"
                        :visible-cells="visibleCells"
                        :explored-cells="exploredCells"
                        :fog-of-war-enabled="fogOfWarEnabled"
                        :detected-tokens="room.room.detected_tokens"
                        :terrain-brush="dmRef?.selected"
                        :light-radius="dmRef?.lightRadius"
                        :bg-image="room.room?.bg_image"
                        :bg-opacity="room.room?.bg_opacity ?? 0.5"
                        :bg-offset-x="room.room?.bg_offset_x"
                        :bg-offset-y="room.room?.bg_offset_y"
                        :bg-scale-x="room.room?.bg_scale_x"
                        :bg-scale-y="room.room?.bg_scale_y"
                        @path-committed="onPath"
                        @cell-click="onCellClick"
                        @token-selected="onTokenSelected"
                        @token-rotate="onTokenRotate"
                        @token-size="onTokenSize"
                        :combat-mode="combatMode"
                        :attack-targets="attackTargets"
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

    <Modal v-if="showSheet" title="我的角色卡" @close="showSheet = false; editingSheetId = null">
      <CharacterSheetEditor :initial-sheet-id="editingSheetId" />
    </Modal>

    <Modal v-if="showUsers && auth.isAdmin" title="用户管理（管理员）" @close="showUsers = false">
      <AdminUserPanel />
    </Modal>

    <!-- 资源库弹窗（待机态）—— 所有人可读，写操作按权限锁（见 ResourceManager / usePermission） -->
    <Modal v-if="showRes" title="资源库" @close="showRes = false">
      <ResourceManager :in-battle="inBattle" @edit-sheet="onSheetEdit" @create-sheet="onSheetCreate" />
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

    <!-- 排名弹窗 -->
    <Modal v-if="showRanking" title="当前排名" @close="showRanking = false">
      <ol class="ranking-list" v-if="rankingData?.ranking?.length">
        <li v-for="(entry, i) in rankingData.ranking" :key="entry.token_id || i" class="ranking-item">
          <span class="rank">{{ i + 1 }}</span>
          <span class="name">{{ entry.name || entry.token_id }}</span>
          <span class="score" v-if="entry.score !== undefined">{{ entry.score }}分</span>
          <span class="status" v-if="entry.is_dead">已淘汰</span>
        </li>
      </ol>
      <p v-else class="empty">暂无排名数据</p>
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
            <li v-for="(s, i) in viewingToken.backpack" :key="i" class="backpack-item">
              <span class="slot-name">{{ s || '—' }}</span>
              <span class="slot-val item-desc" v-if="itemInfo(s)">{{ itemInfo(s)?.description }}</span>
              <button v-if="isOwnToken(viewingToken) && s" class="use-btn" @click="useViewedItem(s)">使用</button>
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
        <!-- 商店货架：只有标记为商店的 NPC 才有 -->
        <div v-if="viewingToken.is_shop" class="section shop">
          <h4>货架 <span class="cp-hint" v-if="selfTokenId">我的金币：{{ room.room?.tokens?.[selfTokenId]?.gold ?? 0 }}</span></h4>
          <ul class="slots" v-if="viewingToken.shop_items?.length">
            <li v-for="name in viewingToken.shop_items" :key="name" class="shop-item">
              <span class="slot-name">{{ name }}</span>
              <span class="slot-val item-desc" v-if="itemInfo(name)">{{ itemInfo(name)?.description }}</span>
              <span class="price">{{ itemInfo(name) ? itemInfo(name)!.price + ' 金币' : '未标价，不可购买' }}</span>
              <button v-if="selfTokenId" class="buy-btn" :disabled="!canBuy(name)" @click="buyFromShop(viewingToken.id, name)">购买</button>
            </li>
          </ul>
          <p v-else class="empty-hint">货架空空如也</p>
        </div>
        <p class="readonly-hint" v-if="!isOwnToken(viewingToken) && !viewingToken.is_shop">只读视图</p>
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
import { useItemStore } from '../stores/items'
import { WSClient, type ServerMessage, type ConnectionStatus } from '../api/ws'
import {
  createRoom, listRooms, fetchMe, updateRoomConfig,
  listMyCharacters, uploadMapBg,
} from '../api/rest'
import { pushToast } from '../composables/useToast'
import { playAnimation } from '../services/diceBoxBridge'
import { useFogOfWar } from '../composables/useFogOfWar'
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

const router = useRouter()
const auth = useAuthStore()
const room = useRoomStore()
const self = useSelfStore()
const chat = useChatStore()
const itemStore = useItemStore()
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
  wsSend({
    type: 'spawn_token',
    payload: { actor_id: payload.actor_id, x: payload.x, y: payload.y },
  })
}

function onSpawnSheet(payload: { sheet: CharacterSheet; x: number; y: number }) {
  const c = payload.sheet
  // 用 owner_id（角色卡真正的归属玩家）拼 token_id，跟玩家自己点格子落子时
  // 用的方案一致（tok_<ownerId>），否则同一个人会因为落子路径不同而冒出两个 token。
  wsSend({
    type: 'place_token',
    payload: {
      token_id: `tok_${c.owner_id}`,
      x: payload.x, y: payload.y,
      character: {
        name: c.name, avatar_url: c.avatar_url, gender: c.gender,
        profession: c.profession, talent: c.talent,
        hp_base: c.hp_base, armor_base: c.armor_base, ap_base: c.ap_base, gold: c.gold,
        backpack: c.backpack, equipment_slots: c.equipment_slots, skill_slots: c.skill_slots,
        darkvision: c.darkvision, vision_range: c.vision_range,
        listen_radius: c.listen_radius, passive_perception: c.passive_perception,
        stealth: c.stealth,
        // 管理员代别人摆放时，归属者是角色卡的主人，不是拖拽操作的管理员本人；
        // 后端只在操作者是管理员时才采信这个字段，非管理员发什么都不算。
        owner_id: c.owner_id,
      },
    },
  })
}

function wsSend(msg: any) {
  applyOptimisticUpdate(msg)
  if (!ws) { console.warn('[ws] not connected, msg dropped:', msg.type); return }
  ws.send(msg)
}

// 乐观更新：发送消息前立即修改本地 store，下次 state_sync 会覆盖为权威状态
function applyOptimisticUpdate(msg: any) {
  if (!room.room) return
  const r = room.room
  const p = msg.payload
  switch (msg.type) {
    case 'move': {
      const t = r.tokens[p.token_id]
      if (t && p.path.length > 0) {
        const [x, y] = p.path[p.path.length - 1]
        t.position = { x, y }
      }
      break
    }
    case 'modify_value': {
      const t = r.tokens[p.token_id]
      if (t) {
        const field = p.field as keyof typeof t
        const val = (t as any)[field]
        if (typeof val === 'number') {
          (t as any)[field] = Math.max(0, val + p.delta)
        }
      }
      break
    }
    case 'add_state': {
      const t = r.tokens[p.token_id]
      if (t) {
        t.states.push({
          id: `opt_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
          name: p.name,
          description: p.description,
          ttl: p.ttl,
        })
      }
      break
    }
    case 'defend': {
      const t = r.tokens[p.token_id]
      if (t) {
        t.ap = Math.max(0, t.ap - (r.config.defend_ap_cost || 1))
      }
      break
    }
    case 'sprint': {
      const t = r.tokens[p.token_id]
      if (t && p.path.length > 0) {
        const [x, y] = p.path[p.path.length - 1]
        t.position = { x, y }
        t.ap = Math.max(0, t.ap - (r.config.sprint_ap_cost || 2))
      }
      break
    }
    case 'use_item': {
      const t = r.tokens[p.token_id]
      if (t) {
        const idx = t.backpack.indexOf(p.item_name)
        if (idx >= 0) t.backpack.splice(idx, 1)
      }
      break
    }
    case 'buy_item': {
      const t = r.tokens[p.buyer_token_id]
      if (t) {
        const info = itemStore.getByName(p.item_name)
        const price = info?.price || 0
        t.gold = Math.max(0, t.gold - price)
        t.backpack.push(p.item_name)
      }
      break
    }
    case 'rotate_token': {
      const t = r.tokens[p.token_id]
      if (t) t.facing = p.facing
      break
    }
    case 'size_token': {
      const t = r.tokens[p.token_id]
      if (t) t.size = Math.max(1, Math.min(4, p.size))
      break
    }
    case 'end_turn': {
      // 不乐观更新回合状态，等服务器同步
      break
    }
    case 'attack': {
      // 攻击涉及骰子和伤害计算，不乐观更新
      break
    }
    // 管理员操作：不乐观更新，等服务器同步
    case 'place_token':
    case 'spawn_token':
    case 'set_terrain':
    case 'set_cell_meta':
    case 'fill_terrain':
    case 'resize_map':
    case 'set_poison_circle':
    case 'set_fog_of_war':
    case 'set_turn_order':
    case 'shuffle_turn_order':
    case 'force_set_actor':
    case 'clear_combat_log':
    case 'start_game':
      break
  }
}

// 攻击目标（多选）+ 玩家本次声明的修正/优势
const attackTargets = ref<string[]>([])
const attackModifier = ref(0)
const attackAdv = ref<'normal' | 'adv' | 'dis'>('normal')

// 从战斗日志里挖出命中 D20 的原始点数（用于 3D 骰子动画）
function extractHitRoll(log: any): number | null {
  for (const r of log.results || []) {
    for (const e of r.effects || []) {
      if (e.hit && typeof e.hit.roll === 'number') return e.hit.roll
    }
  }
  return null
}

function onCombatMode(mode: 'attack' | 'sprint' | null) {
  combatMode.value = mode
  if (mode !== 'attack') attackTargets.value = []
}

function onAttackTarget(targetId: string) {
  toggleAttackTarget(targetId)
}

function toggleAttackTarget(id: string) {
  const i = attackTargets.value.indexOf(id)
  if (i >= 0) attackTargets.value.splice(i, 1)
  else attackTargets.value.push(id)
}

function confirmAttack() {
  const attacker = selfTokenId.value
  if (!attacker || !attackTargets.value.length) return
  // 逐个目标发起攻击（每次消耗 1AP，后端按规则校验，AP 不足会被拒）；带上玩家声明的修正/优势
  const advMap = { normal: '', adv: 'adv', dis: 'dis' } as const
  for (const tid of attackTargets.value) {
    wsSend({ type: 'attack', payload: {
      attacker_id: attacker, defender_id: tid,
      modifier: attackModifier.value || 0, advantage: advMap[attackAdv.value],
    } })
  }
  attackTargets.value = []
  combatMode.value = null
  combatRef.value?.setMode(null)
}

function cancelAttack() {
  attackTargets.value = []
  combatMode.value = null
  combatRef.value?.setMode(null)
}

function onSheetEdit(sheet: any) {
  editingSheetId.value = sheet.id
  showSheet.value = true
}
function onSheetCreate() {
  editingSheetId.value = null
  showSheet.value = true
}

// --- 战役状态 ---
const inBattle = computed(() => !!room.room)
const chatChannels = computed(() =>
  inBattle.value
    ? ['hall', 'private', 'battle', 'spatial', 'war_hall']
    : ['hall', 'private']
)

const showResPanel = ref(false)

// --- 弹窗 ---
const showCreate = ref(false); const showJoin = ref(false)
const showSheet = ref(false); const showUsers = ref(false)
const editingSheetId = ref<string | null>(null)
const showRes = ref(false); const showSheetPicker = ref(false)
const showRanking = ref(false)
const rankingData = ref<{ ranking: any[]; elimination_order: string[] } | null>(null)
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
  try { rooms.value = await listRooms() }
  catch (e: any) { pushToast(`获取房间列表失败：${e.message || e}`) }
}

async function doCreateRoom() {
  createError.value = ''
  if (!newRoomName.value) { createError.value = '请输入战役名'; return }
  try {
    const r = await createRoom(newRoomName.value)
    // 更新地图尺寸
    if (newMapW.value !== 30 || newMapH.value !== 30) {
      try { await updateRoomConfig(r.id, { map_width: newMapW.value, map_height: newMapH.value }) }
      catch (e: any) { pushToast(`战役已创建，但地图尺寸设置失败：${e.message || e}`, 'warn') }
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

const wsStatus = ref<ConnectionStatus>('closed')

// --- 战争迷雾 ---
const fow = useFogOfWar()
const exploredCells = computed<Set<string>>(() => fow.exploredCells.value)
const fogOfWarEnabled = computed(() => room.room?.config.fog_of_war_enabled ?? false)

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
    wsSend(detail)
  }
  window.addEventListener('ws-send', wsSendHandler)
  ws.onMessage(dispatchMessage)
  ws.onStatus((s) => {
    const prev = wsStatus.value
    wsStatus.value = s
    if (s === 'reconnecting' && prev === 'open') {
      pushToast('与服务器断开连接，正在尝试重连…', 'warn', 8000)
    } else if (s === 'open' && prev === 'reconnecting') {
      pushToast('已重新连接', 'info', 2500)
    }
  })
  ws.connect(roomId, auth.token!)
  // 加载本局战争迷雾记忆
  fow.load(roomId, auth.user?.id || '')
}

function disconnectWs() {
  if (wsSendHandler) { window.removeEventListener('ws-send', wsSendHandler); wsSendHandler = null }
  if (ws) { ws.close(); ws = null }
  wsStatus.value = 'closed'
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
  if (m.type === 'state_sync') {
    // DEBUG: 确认 bg_image 是否从后端到达
    if (m.payload.bg_image !== undefined) {
      console.log('[bg] state_sync bg_image =', m.payload.bg_image?.substring(0, 80))
    }
    room.setState(m.payload)
    // 记录探索记忆
    if (m.payload.visible_cells && !auth.isAdmin) {
      const newCells = new Set<string>(m.payload.visible_cells.map(([x, y]: [number, number]) => `${x},${y}`))
      const changed = fow.markExplored(newCells)
      if (changed) {
        fow.persist(m.payload.id, auth.user?.id || '')
      }
    }
  }
  else if (m.type === 'chat') chat.addMessage(m.payload)
  else if (m.type === 'combat_log') {
    combatRef.value?.addLog(m.payload)
    // 我发起的攻击 → 把命中 D20 用 3D 骰子甩出来（玩家看得到落点；结果仍是服务端权威的）
    if (m.payload.actor_id === selfTokenId.value) {
      const roll = extractHitRoll(m.payload)
      if (roll != null) playAnimation([{ sides: 20, value: roll }]).catch(() => {})
    }
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
  else if (m.type === 'item_used') {
    pushToast(`${nameOfToken(m.payload.token_id)} 使用了「${m.payload.item}」`, 'info')
  }
  else if (m.type === 'item_bought') {
    pushToast(`${nameOfToken(m.payload.token_id)} 花了 ${m.payload.price} 金币买到「${m.payload.item}」`, 'info')
  }
  else if (m.type === 'error') {
    pushToast(m.payload?.message || '操作失败', 'error')
  }
  else if (m.type === 'ranking') {
    // Phase 2: 接收服务端排名快照，弹窗展示
    rankingData.value = m.payload
    showRanking.value = true
  }
}

function nameOfToken(tokenId: string): string {
  return room.room?.tokens?.[tokenId]?.character_name || tokenId
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
      // click-to-move：棋子已选中，点目标格即可移动
      pushToast('点击目标格即可移动该棋子', 'info')
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
  wsSend({
    type: 'place_token',
    payload: {
      token_id: `tok_${auth.user?.id}`,
      x: cell.x, y: cell.y,
      character: {
        name: c.name, avatar_url: c.avatar_url, gender: c.gender, profession: c.profession, talent: c.talent,
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
  // 疾跑模式：交给 CombatPanel 自己处理（跟 attack 走同一套委托模式），
  // 它会发 sprint 消息并把 mode 清掉——之前这里完全没判断 combatMode，
  // 永远当成普通 move 发出去，疾跑按钮点了也没用，模式提示还永远不消失。
  if (combatMode.value === 'sprint') {
    combatRef.value?.onSprintPath(path)
    return
  }
  const targetId = selectedToken.value?.id || selfTokenId.value
  if (!targetId) return
  wsSend({ type: 'move', payload: { token_id: targetId, path } })
}

function onTokenSelected(t: any) {
  // 攻击模式：点击敌方 token 切换为目标（可多选），不立即攻击
  if (combatMode.value === 'attack') {
    const selfId = selfTokenId.value
    if (t.id !== selfId && !t.is_dead) {
      toggleAttackTarget(t.id)
    }
    return
  }
  selectedToken.value = t
}

function onTokenRotate(tokenId: string, facing: number) {
  wsSend({ type: 'rotate_token', payload: { token_id: tokenId, facing } })
}

function onTokenSize(tokenId: string, size: number) {
  wsSend({ type: 'size_token', payload: { token_id: tokenId, size } })
}

const viewingToken = ref<any>(null)
function onTokenDblClick(token: any) {
  viewingToken.value = token
  itemStore.load()
}

function isOwnToken(token: any): boolean {
  return !!token && token.id === selfTokenId.value
}

function itemInfo(name: string) {
  return name ? itemStore.getByName(name) : undefined
}

function useViewedItem(itemName: string) {
  if (!viewingToken.value) return
  wsSend({ type: 'use_item', payload: { token_id: viewingToken.value.id, item_name: itemName } })
}

function canBuy(itemName: string): boolean {
  if (!selfTokenId.value) return false
  const info = itemInfo(itemName)
  if (!info || info.price <= 0) return false
  const myGold = room.room?.tokens?.[selfTokenId.value]?.gold ?? 0
  return myGold >= info.price
}

function buyFromShop(shopTokenId: string, itemName: string) {
  if (!selfTokenId.value) return
  wsSend({
    type: 'buy_item',
    payload: { buyer_token_id: selfTokenId.value, shop_token_id: shopTokenId, item_name: itemName },
  })
}

// --- 监听未落子时自动弹选角色卡 ---
// 管理员不落子；玩家仅在 DM 开启 allow_player_placement 时才弹
function checkPlacementNeeded() {
  if (auth.isAdmin) return
  const allowed = room.room?.config?.allow_player_placement ?? false
  if (!allowed) return
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
  wsSend({ type: 'set_poison_circle', payload: cfg })
}

function onSetFogOfWar(enabled: boolean) {
  wsSend({ type: 'set_fog_of_war', payload: { enabled } })
}
function onSetPlayerPlacement(enabled: boolean) {
  wsSend({ type: 'set_player_placement', payload: { enabled } })
}
function onSetFreeMode(enabled: boolean) {
  wsSend({ type: 'set_free_mode', payload: { enabled } })
}
function onRandomPlacement(mode: string, area?: { x1: number; y1: number; x2: number; y2: number }) {
  const payload: any = { mode }
  if (area) payload.area = area
  wsSend({ type: 'random_placement', payload })
}

function onSetTurnOrder(order: string[]) {
  wsSend({ type: 'set_turn_order', payload: { order } })
}
function onShuffleTurn() {
  wsSend({ type: 'shuffle_turn_order', payload: {} })
}
function onForceActor(tokenId: string) {
  wsSend({ type: 'force_set_actor', payload: { token_id: tokenId } })
}
function onClearCombatLog() {
  wsSend({ type: 'clear_combat_log', payload: {} })
}

function onMapResize(w: number, h: number) {
  wsSend({ type: 'resize_map', payload: { width: w, height: h } })
}
function onFillArea(area: { x1: number; y1: number; x2: number; y2: number; type: string }) {
  wsSend({ type: 'fill_terrain', payload: area })
}

// --- 底图导入（HTTP 上传拿 URL，再通过 ws 广播给全员）---
const bgUploading = ref(false)
function onBgUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  bgUploading.value = true
  uploadMapBg(file).then(url => {
    console.log('[bg] uploaded, url =', url)
    wsSend({ type: 'set_bg_image', payload: { image: url } })
    console.log('[bg] wsSend set_bg_image sent')
  }).catch(err => {
    pushToast(err.message || '底图上传失败', 'error')
  }).finally(() => {
    bgUploading.value = false
  })
  input.value = ''  // 允许再次选同一文件
}

function onBgOpacityInput(e: Event) {
  const v = parseFloat((e.target as HTMLInputElement).value)
  wsSend({ type: 'set_bg_image', payload: { opacity: v } })
}

function onBgTransform(t: { offset_x: number; offset_y: number; scale_x: number; scale_y: number }) {
  wsSend({ type: 'set_bg_image', payload: t })
}

function clearBgImage() {
  wsSend({ type: 'set_bg_image', payload: { image: null } })
}

onMounted(async () => {
  try { await fetchMe() } catch { auth.logout(); router.push('/login'); return }
  await refreshRooms()
})

// 监听 room 变化，自动触发落子提示
watch(() => room.room, (r) => {
  if (r) checkPlacementNeeded()
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
.conn-banner { padding: 4px 16px; background: #7a3b00; color: #fff; font-size: 12px; text-align: center; }
.actions button { padding: 6px 12px; background: #444; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; font-size: 13px; }
.actions button:hover { background: #555; }
.body { display: grid; grid-template-columns: 240px 1fr 320px; flex: 1; min-height: 0; }
.left-panel { overflow-y: auto; padding: 8px; background: #fafafa; border-right: 1px solid #ccc; }
.center-panel { display: flex; flex-direction: column; min-width: 0; }
.canvas-wrap { flex: 1; overflow: auto; padding: 8px; background: #eee; }
.canvas-wrap.placing-mode { cursor: crosshair; }
.attack-bar { display: flex; align-items: center; gap: 10px; padding: 6px 12px;
  background: #2a1010; color: #fff; border-bottom: 1px solid #500; font-size: 13px; }
.attack-bar .ab-hint { color: #f99; }
.attack-bar .ab-mod { color: #fcc; display: flex; align-items: center; gap: 4px; }
.attack-bar .ab-mod input { width: 48px; padding: 2px 4px; border: 1px solid #844; border-radius: 3px; background: #1a0808; color: #fff; }
.attack-bar .ab-adv { padding: 2px 4px; border: 1px solid #844; border-radius: 3px; background: #1a0808; color: #fff; }
.attack-bar .ab-count { color: #fa0; font-weight: bold; }
.attack-bar .ab-confirm { margin-left: auto; padding: 4px 14px; background: #c33; color: #fff;
  border: none; border-radius: 3px; cursor: pointer; font-weight: bold; }
.attack-bar .ab-confirm:disabled { background: #633; cursor: not-allowed; opacity: 0.6; }
.attack-bar .ab-cancel { padding: 4px 12px; background: #444; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; }
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
:deep(.modal-body) .ranking-list { list-style: none; padding: 0; margin: 0; min-width: 300px; }
:deep(.modal-body) .ranking-item { display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
:deep(.modal-body) .ranking-item .rank { width: 24px; height: 24px; line-height: 24px;
  text-align: center; background: #0f3460; color: #fff; border-radius: 50%; font-size: 12px; }
:deep(.modal-body) .ranking-item .name { flex: 1; color: #333; }
:deep(.modal-body) .ranking-item .score { color: #6a3; font-weight: bold; }
:deep(.modal-body) .ranking-item .status { color: #c33; font-size: 11px; }
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
:deep(.modal-body) .token-view .backpack-item,
:deep(.modal-body) .token-view .shop-item { flex-wrap: wrap; gap: 4px; align-items: center; }
:deep(.modal-body) .token-view .item-desc { color: #999; font-size: 11px; flex: 1; }
:deep(.modal-body) .token-view .use-btn,
:deep(.modal-body) .token-view .buy-btn { padding: 2px 8px; font-size: 11px; border: none;
  border-radius: 3px; cursor: pointer; background: #0f3460; color: #fff; }
:deep(.modal-body) .token-view .buy-btn:disabled { opacity: 0.4; cursor: not-allowed; }
:deep(.modal-body) .token-view .section.shop h4 { display: flex; justify-content: space-between; align-items: center; }
:deep(.modal-body) .token-view .section.shop .cp-hint { color: #3a7; font-size: 11px; font-weight: normal; }
:deep(.modal-body) .token-view .price { color: #a70; font-size: 11px; white-space: nowrap; }
:deep(.modal-body) .token-view .empty-hint { color: #bbb; font-size: 12px; text-align: center; padding: 8px 0; }

.damage-flash { position: fixed; inset: 0; pointer-events: none; z-index: 9999;
  box-shadow: inset 0 0 80px rgba(200, 0, 0, 0.4); opacity: 0; transition: opacity 0.3s; }
.damage-flash.shake { opacity: 1; animation: shake 0.5s ease-in-out; }
@keyframes shake { 0%,100% { transform: translate(0,0); } 20% { transform: translate(-4px,2px); } 40% { transform: translate(4px,-2px); } 60% { transform: translate(-2px,4px); } 80% { transform: translate(2px,-4px); } }
/* 资源库侧边栏 — 收窄到 200px */
.res-panel { position: fixed; left: 0; top: 48px; bottom: 0; width: 300px; background: #f8f9fa; border-right: 1px solid #ddd; z-index: 50; display: flex; flex-direction: column; }
.res-panel-head { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; background: #0f3460; color: #fff; font-size: 13px; font-weight: 600; flex-shrink: 0; }
.res-panel-head .res-close { background: none; border: none; color: #fff; font-size: 18px; cursor: pointer; line-height: 1; }
.res-panel-body { flex: 1; overflow-y: auto; padding: 8px; }
.res-toggle { position: fixed; left: 0; top: 50%; transform: translateY(-50%); z-index: 49; padding: 6px; background: #0f3460; color: #fff; border: none; border-radius: 0 4px 4px 0; cursor: pointer; font-size: 14px; }

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
}
</style>
