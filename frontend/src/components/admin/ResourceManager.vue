<template>
  <div class="res-mgr">
    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" @click="active = t.key"
              :class="{ active: active === t.key }">{{ t.label }}</button>
    </div>

    <!-- 我的角色卡（所有人）-->
    <div v-if="active === 'mysheets'" class="panel">
      <div class="add-form">
        <button class="add-btn" @click="emit('create-sheet')">+ 新建角色卡</button>
      </div>
      <div v-if="mySheetsLoading" class="loading">加载中...</div>
      <ul v-else class="actor-list">
        <li v-for="s in mySheets" :key="s.id" class="actor-card"
            draggable="true" @dragstart="onSheetDragStart($event, s)"
            @click="emit('edit-sheet', s)"
            :title="`拖拽「${s.name}」到地图落子，或点击编辑`">
          <img v-if="s.avatar_url" :src="s.avatar_url" class="actor-avatar" />
          <div v-else class="actor-avatar placeholder">{{ s.name[0] || '?' }}</div>
          <div class="actor-info">
            <div class="actor-name">{{ s.name || '未命名' }}</div>
            <div class="actor-meta">{{ s.profession || '—' }} · HP{{ s.hp_base }} · 甲{{ s.armor_base }} · AP{{ s.ap_base }}</div>
          </div>
          <div class="drag-hint">⋮⋮</div>
        </li>
        <li v-if="!mySheets.length" class="empty">还没有角色卡，点上方「+ 新建角色卡」创建一张</li>
      </ul>
    </div>

    <!-- 角色卡库 -->
    <div v-if="active === 'sheets'" class="panel">
      <div v-if="sheetsLoading" class="loading">加载中...</div>
      <ul v-else class="sheet-list">
        <li v-for="s in sheets" :key="s.id" @click="toggleSheet(s.id)"
            :class="{ expanded: expandedSheet === s.id }">
          <div class="row-head">
            <strong>{{ s.name }}</strong>
            <span class="meta">{{ s.profession }} · HP{{ s.hp_base }} 甲{{ s.armor_base }}</span>
            <span class="badge" v-if="s.darkvision">暗视</span>
          </div>
          <div v-if="expandedSheet === s.id" class="detail">
            <div class="kv">
              <span>性别:{{ s.gender || '—' }}</span>
              <span>天赋:{{ s.talent || '—' }}</span>
              <span>金币:{{ s.gold }}</span>
              <span>视野:{{ (s as any).vision_range }}</span>
              <span>觉察:{{ (s as any).listen_radius }}/{{ (s as any).passive_perception }}</span>
              <span>隐匿:{{ (s as any).stealth }}</span>
              <span>归属:{{ (s as any).nickname || '未分配' }}</span>
            </div>
            <div class="slots" v-if="s.equipment_slots?.length">
              <h6>装备</h6>
              <span v-for="(e, i) in s.equipment_slots" :key="i" class="chip">{{ e || '空' }}</span>
            </div>
            <div class="slots" v-if="s.skill_slots?.length">
              <h6>技能</h6>
              <span v-for="(e, i) in s.skill_slots" :key="i" class="chip">{{ e || '空' }}</span>
            </div>
            <div class="slots" v-if="s.backpack?.length">
              <h6>背包</h6>
              <span v-for="(e, i) in s.backpack" :key="i" class="chip">{{ e }}</span>
            </div>
            <div class="secret" v-if="s.secret_backups?.length">
              <h6>底牌</h6>
              <p v-for="(b, i) in s.secret_backups" :key="i">{{ b }}</p>
            </div>
          </div>
        </li>
        <li v-if="!sheets.length" class="empty">暂无角色卡</li>
      </ul>
    </div>

    <!-- 怪物模板库 -->
    <div v-if="active === 'monsters'" class="panel">
      <div class="add-form" v-if="canManageLibrary">
        <input v-model="newMonster.name" placeholder="怪物名称" />
        <input type="number" v-model.number="newMonster.hp" placeholder="HP" />
        <input type="number" v-model.number="newMonster.armor" placeholder="护甲" />
        <input type="number" v-model.number="newMonster.vision_range" placeholder="视野" />
        <label class="mini-check">
          <input type="checkbox" v-model="newMonster.darkvision" /> 暗视
        </label>
        <button @click="addMonster">添加</button>
      </div>
      <ul class="tmpl-list">
        <li v-for="(m, i) in monsters" :key="i">
          <strong>{{ m.name }}</strong>
          <span class="meta">HP{{ m.hp }} 甲{{ m.armor }} 视{{ m.vision_range }}
            <span v-if="m.darkvision" class="badge">暗视</span></span>
          <button v-if="canManageLibrary" class="del" @click="monsters.splice(i, 1)">删</button>
        </li>
        <li v-if="!monsters.length" class="empty">暂无怪物模板</li>
      </ul>
    </div>

    <!-- 装备池 -->
    <div v-if="active === 'equip'" class="panel">
      <div class="add-form" v-if="canManageLibrary">
        <input v-model="newEquip" placeholder="装备/外挂名称" @keyup.enter="addEquip" />
        <button @click="addEquip">添加</button>
      </div>
      <div class="chip-pool">
        <span v-for="(e, i) in equips" :key="i" class="chip" :class="{ removable: canManageLibrary }"
              @click="canManageLibrary && equips.splice(i, 1)">
          {{ e }} <span v-if="canManageLibrary">✕</span>
        </span>
        <span v-if="!equips.length" class="empty">暂无装备</span>
      </div>
    </div>

    <!-- 角色卡模板（Actor 库）-->
    <div v-if="active === 'actors'" class="panel">
      <div class="add-form">
        <button v-if="canManageLibrary" @click="newActor" class="add-btn">+ 新建角色</button>
        <input v-model="actorFilter" placeholder="搜索..." class="search-input" />
      </div>
      <div v-if="actorStore.actors.length === 0" class="empty">暂无角色卡模板<br/><small v-if="canSpawnFromLibrary">新建后可拖拽到地图生成 Token</small></div>
      <ul class="actor-list">
        <li v-for="a in filteredActors" :key="a.id" class="actor-card"
            :class="{ dragging: dragActorId === a.id }"
            :draggable="canSpawnFromLibrary" @dragstart="onActorDragStart($event, a)" @dragend="dragActorId = null"
            @click="canManageLibrary && editActor(a)"
            :title="canSpawnFromLibrary ? `拖拽「${a.name}」到地图投放` : a.name">
          <img v-if="a.avatar_url" :src="a.avatar_url" class="actor-avatar" />
          <div v-else class="actor-avatar placeholder">{{ a.name[0] }}</div>
          <div class="actor-info">
            <div class="actor-name">{{ a.name }}</div>
            <div class="actor-meta">{{ typeLabel(a.type) }} · HP{{ a.hp }}/{{ a.max_hp }} · 甲{{ a.armor }}</div>
          </div>
          <div class="actor-actions" v-if="canManageLibrary">
            <button class="mini-btn" @click.stop="duplicateActor(a)">复制</button>
            <button class="mini-btn danger" @click.stop="deleteActor(a.id)">删</button>
          </div>
        </li>
      </ul>

      <!-- Actor 编辑/新建表单 -->
      <div v-if="showActorForm" class="modal-overlay" @click.self="showActorForm = false">
        <div class="modal-box">
          <h3>{{ editingActor ? '编辑角色' : '新建角色' }}</h3>
          <div class="form-grid">
            <label>名称 <input v-model="actorForm.name" /></label>
            <label>类型
              <select v-model="actorForm.type">
                <option value="player">玩家</option>
                <option value="npc">NPC</option>
                <option value="monster">怪物</option>
              </select>
            </label>
            <label>头像URL <input v-model="actorForm.avatar_url" placeholder="可选" /></label>
            <label class="avatar-upload">
              或上传头像
              <input type="file" accept="image/*" @change="onAvatarUpload" />
            </label>
            <div v-if="actorForm.avatar_url" class="avatar-preview">
              <img :src="actorForm.avatar_url" />
            </div>
            <label>HP <input v-model.number="actorForm.hp" type="number" /></label>
            <label>最大HP <input v-model.number="actorForm.max_hp" type="number" /></label>
            <label>护甲 <input v-model.number="actorForm.armor" type="number" /></label>
            <label>AP <input v-model.number="actorForm.ap" type="number" /></label>
            <label>最大AP <input v-model.number="actorForm.max_ap" type="number" /></label>
            <label>视野 <input v-model.number="actorForm.vision_range" type="number" /></label>
            <label>暗视 <input v-model.number="actorForm.darkvision" type="number" /></label>
            <label>听觉范围 <input v-model.number="actorForm.listen_radius" type="number" /></label>
            <label>被动觉察 <input v-model.number="actorForm.passive_perception" type="number" /></label>
            <label>潜行 <input v-model.number="actorForm.stealth" type="number" /></label>
          </div>
          <div v-if="actorForm.type === 'npc'" class="shop-config">
            <label class="mini-check">
              <input type="checkbox" v-model="actorForm.is_shop" /> 这是一个商店（玩家可以跟它买道具）
            </label>
            <div v-if="actorForm.is_shop" class="shop-items-pick">
              <p class="hint">货架（点击道具加入/移出，没有价格的道具不会显示出来给玩家买）</p>
              <div class="chip-pool">
                <span v-for="i in itemStore.items" :key="i.id" class="chip pick"
                      :class="{ active: actorForm.shop_items?.includes(i.name) }"
                      @click="toggleShopItem(i.name)">
                  {{ i.name }}<span v-if="i.price <= 0"> (未标价)</span>
                </span>
                <span v-if="!itemStore.items.length" class="empty">道具库是空的，先去"道具库"标签建几个道具</span>
              </div>
            </div>
          </div>
          <div class="form-actions">
            <button @click="saveActor" class="save-btn">保存</button>
            <button @click="showActorForm = false" class="cancel-btn">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 道具库 -->
    <div v-if="active === 'items'" class="panel">
      <div class="add-form">
        <button v-if="canManageLibrary" @click="newItem" class="add-btn">+ 新建道具</button>
        <input v-model="itemFilter" placeholder="搜索..." class="search-input" />
      </div>
      <div v-if="itemStore.items.length === 0" class="empty">暂无道具<br/><small v-if="canManageLibrary">新建后可以挂在 NPC 商店货架上出售</small></div>
      <ul class="actor-list">
        <li v-for="i in filteredItems" :key="i.id" class="actor-card" @click="canManageLibrary && editItem(i)">
          <img v-if="i.icon_url" :src="i.icon_url" class="actor-avatar" />
          <div v-else class="actor-avatar placeholder">{{ i.name[0] }}</div>
          <div class="actor-info">
            <div class="actor-name">{{ i.name }} <span class="badge">{{ categoryLabel(i.category) }}</span></div>
            <div class="actor-meta">{{ i.description || '无描述' }} · {{ i.price > 0 ? i.price + ' 金币' : '不可购买' }}</div>
          </div>
          <div class="actor-actions" v-if="canManageLibrary">
            <button class="mini-btn danger" @click.stop="deleteItem(i.id)">删</button>
          </div>
        </li>
      </ul>

      <div v-if="showItemForm" class="modal-overlay" @click.self="showItemForm = false">
        <div class="modal-box">
          <h3>{{ editingItem ? '编辑道具' : '新建道具' }}</h3>
          <div class="form-grid">
            <label>名称 <input v-model="itemForm.name" /></label>
            <label>分类
              <select v-model="itemForm.category">
                <option value="weapon">武器</option>
                <option value="armor">护甲</option>
                <option value="consumable">消耗品</option>
                <option value="skill">技能</option>
                <option value="misc">杂项</option>
              </select>
            </label>
            <label>价格（0=不可购买） <input v-model.number="itemForm.price" type="number" /></label>
            <label>图标URL <input v-model="itemForm.icon_url" placeholder="可选" /></label>
            <label style="grid-column: 1 / -1">描述 <input v-model="itemForm.description" /></label>
            <label style="grid-column: 1 / -1">效果说明（团主参考，系统不解析）
              <input v-model="itemForm.effect_text" />
            </label>
          </div>
          <div class="form-actions">
            <button @click="saveItem" class="save-btn">保存</button>
            <button @click="showItemForm = false" class="cancel-btn">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 内容库（所有人只读）：事件/陷阱/怪物/奇遇/NPC -->
    <div v-if="active === 'library'" class="panel">
      <div class="lib-cats">
        <button v-for="c in libCats" :key="c.key"
                :class="{ active: libCategory === c.key }" @click="libCategory = c.key">{{ c.label }}</button>
      </div>
      <div class="add-form">
        <input v-model="libFilter" placeholder="搜索内容库..." class="search-input" />
        <button class="lib-io" @click="exportLibrary" :disabled="!libEntries.length"
                title="导出全部内容库为 JSON（即导入用的规范格式）">⬇ 导出</button>
        <label v-if="canManageLibrary" class="lib-io import"
               title="导入 JSON 数组（与导出同格式，id 可省略，按 id 合并）">
          {{ libImporting ? '导入中…' : '⬆ 导入' }}
          <input type="file" accept="application/json,.json" @change="onImportLibrary" hidden />
        </label>
        <span class="lib-count">{{ filteredLibrary.length }}/{{ libEntries.length }}</span>
      </div>
      <div v-if="libLoading" class="loading">加载中...</div>
      <ul v-else class="sheet-list">
        <li v-for="e in filteredLibrary" :key="e.id" @click="toggleLib(e.id)"
            :class="{ expanded: expandedLib === e.id }">
          <div class="row-head">
            <strong>{{ e.name }}</strong>
            <span v-if="e.tier" class="badge">{{ e.tier }}</span>
            <span class="meta">{{ e.effect_text }}</span>
          </div>
          <div v-if="expandedLib === e.id" class="detail">
            <div class="kv">
              <span v-for="(v, k) in e.fields" :key="k"><b>{{ k }}：</b>{{ v || '—' }}</span>
            </div>
            <p v-if="e.note" class="lib-note">备注：{{ e.note }}</p>
          </div>
        </li>
        <li v-if="!filteredLibrary.length" class="empty">无匹配条目</li>
      </ul>
    </div>

    <!-- 抽取表（所有人可抽，增删改仅管理员）-->
    <div v-if="active === 'rolltable'" class="panel">
      <div class="add-form">
        <button v-if="canManageLibrary" class="add-btn" @click="newTable">+ 新建抽取表</button>
      </div>
      <div v-if="lastDraw" class="draw-result">
        🎲 <b>{{ lastDraw.table_name }}</b> →
        <span class="draw-text">{{ lastDraw.text }}</span>
        <span v-if="lastDraw.entry && lastDraw.entry.tier" class="badge">{{ lastDraw.entry.tier }}</span>
        <div v-if="lastDraw.entry && lastDraw.entry.effect_text" class="draw-eff">{{ lastDraw.entry.effect_text }}</div>
      </div>
      <ul class="actor-list">
        <li v-for="t in rollTables" :key="t.id" class="actor-card">
          <div class="actor-info">
            <div class="actor-name">{{ t.name }}</div>
            <div class="actor-meta">
              {{ t.description }}
              <span class="badge">{{ t.source_category ? '内容库·' + rtCatLabel(t.source_category) : t.entries.length + ' 条目' }}</span>
            </div>
          </div>
          <div class="actor-actions">
            <button class="mini-btn draw-btn" @click="doDraw(t)">🎲 抽取</button>
            <button v-if="canManageLibrary" class="mini-btn" @click="editTable(t)">编辑</button>
            <button v-if="canManageLibrary" class="mini-btn danger" @click="removeTable(t)">删</button>
          </div>
        </li>
        <li v-if="!rollTables.length" class="empty">暂无抽取表<br/><small v-if="canManageLibrary">新建一张：可从内容库分类随机抽，或自定义加权条目</small></li>
      </ul>

      <div v-if="showTableForm" class="modal-overlay" @click.self="showTableForm = false">
        <div class="modal-box">
          <h3>{{ editingTable ? '编辑抽取表' : '新建抽取表' }}</h3>
          <div class="form-grid">
            <label style="grid-column:1/-1">名称 <input v-model="tableForm.name" /></label>
            <label style="grid-column:1/-1">说明 <input v-model="tableForm.description" /></label>
            <label style="grid-column:1/-1">抽取来源
              <select v-model="tableForm.source_category">
                <option value="">自定义加权条目</option>
                <option value="event">内容库·事件</option>
                <option value="trap">内容库·陷阱</option>
                <option value="monster">内容库·怪物</option>
                <option value="adventure">内容库·奇遇</option>
                <option value="npc">内容库·NPC</option>
              </select>
            </label>
          </div>
          <div v-if="!tableForm.source_category" class="rt-entries">
            <p class="hint">加权条目（weight 越大越容易抽到）</p>
            <div v-for="(en, i) in tableForm.entries" :key="i" class="rt-entry-row">
              <input type="number" v-model.number="en.weight" min="1" class="rt-weight" />
              <input v-model="en.text" placeholder="结果文字" class="rt-text" />
              <button class="del" @click="tableForm.entries.splice(i, 1)">×</button>
            </div>
            <button class="mini-btn" @click="tableForm.entries.push({ weight: 1, text: '' })">+ 加一条</button>
          </div>
          <div class="form-actions">
            <button class="save-btn" @click="saveTable">保存</button>
            <button class="cancel-btn" @click="showTableForm = false">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 光源/物件模板 -->
    <div v-if="active === 'objects'" class="panel">
      <div class="add-form" v-if="canManageLibrary">
        <input v-model="newObj.name" placeholder="物件名（火把/篝火/宝箱...）" />
        <select v-model="newObj.kind">
          <option value="light">光源</option>
          <option value="container">容器/宝箱</option>
          <option value="decor">装饰</option>
        </select>
        <input v-if="newObj.kind === 'light'" type="number"
               v-model.number="newObj.light_radius" placeholder="光半径" min="1" max="10" />
        <button @click="addObj">添加</button>
      </div>
      <ul class="tmpl-list">
        <li v-for="(o, i) in objects" :key="i">
          <strong>{{ o.name }}</strong>
          <span class="meta">{{ kindLabel(o.kind) }}<span v-if="o.kind === 'light'"> · 半径{{ o.light_radius }}</span></span>
          <button v-if="canManageLibrary" class="del" @click="objects.splice(i, 1)">删</button>
        </li>
        <li v-if="!objects.length" class="empty">暂无物件模板</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { listAllCharacters, listMyCharacters, listLibrary, importLibrary, uploadAvatar,
  listRollTables, createRollTable, updateRollTable, deleteRollTable, drawRollTable } from '../../api/rest'
import type { CharacterSheet, Actor, ActorCreate, Item, ItemCreate, LibraryEntry, RollTable, DrawResult } from '../../api/types'
import { pushToast } from '../../composables/useToast'
import { monsters, equips, objects } from '../../stores/resources'
import { useActorStore } from '../../stores/actors'
import { useItemStore } from '../../stores/items'
import { usePermission } from '../../composables/usePermission'

const actorStore = useActorStore()
const itemStore = useItemStore()
// 所有人都能读资源库；写操作（增删改）和拖拽落子按权限锁，角色卡库仅管理员可见。
const { canManageLibrary, canSpawnFromLibrary, canViewAllSheets } = usePermission()

const emit = defineEmits<{
  (e: 'edit-sheet', sheet: CharacterSheet): void
  (e: 'create-sheet'): void
}>()
const props = defineProps<{ inBattle?: boolean }>()

const allTabs = [
  { key: 'mysheets', label: '我的角色卡' },
  { key: 'sheets', label: '角色卡库' },
  { key: 'actors', label: '角色模板' },
  { key: 'items', label: '道具库' },
  { key: 'library', label: '内容库' },
  { key: 'rolltable', label: '抽取表' },
  { key: 'monsters', label: '怪物模板' },
  { key: 'equip', label: '装备池' },
  { key: 'objects', label: '物件' },
]
// 「角色卡库」含他人底牌仅管理员可见；其余（含「我的角色卡」）对所有人开放
const tabs = computed(() => allTabs.filter((t) => t.key !== 'sheets' || canViewAllSheets.value))
const active = ref('mysheets')

// 角色卡库
const sheets = ref<CharacterSheet[]>([])
const sheetsLoading = ref(false)
const expandedSheet = ref<string | null>(null)

async function loadSheets() {
  sheetsLoading.value = true
  try { sheets.value = await listAllCharacters() }
  catch (e) { console.warn(e) }
  finally { sheetsLoading.value = false }
}
function toggleSheet(id: string) {
  expandedSheet.value = expandedSheet.value === id ? null : id
}

// ---- 我的角色卡（所有人）：列出本人角色卡，可拖到地图落子 / 点开编辑 / 新建 ----
const mySheets = ref<CharacterSheet[]>([])
const mySheetsLoading = ref(false)
async function loadMySheets() {
  mySheetsLoading.value = true
  try { mySheets.value = await listMyCharacters() }
  catch (e) { console.warn(e) }
  finally { mySheetsLoading.value = false }
}
function onSheetDragStart(e: DragEvent, s: CharacterSheet) {
  e.dataTransfer?.setData('application/json', JSON.stringify({ kind: 'character_sheet', sheet: s }))
  e.dataTransfer!.effectAllowed = 'copy'
}

// 怪物模板（共享 store）
interface MonsterTmpl { name: string; hp: number; armor: number; vision_range: number; darkvision: boolean }
const newMonster = ref<MonsterTmpl>({ name: '', hp: 30, armor: 3, vision_range: 5, darkvision: false })

function addMonster() {
  if (!newMonster.value.name.trim()) return
  monsters.value.push({ ...newMonster.value })
  newMonster.value = { name: '', hp: 30, armor: 3, vision_range: 5, darkvision: false }
}

// 装备池（共享 store）
const newEquip = ref('')
function addEquip() {
  const v = newEquip.value.trim()
  if (!v) return
  if (!equips.value.includes(v)) equips.value.push(v)
  newEquip.value = ''
}

// 物件模板（共享 store）
interface ObjTmpl { name: string; kind: 'light' | 'container' | 'decor'; light_radius?: number }
const newObj = ref<ObjTmpl>({ name: '', kind: 'light', light_radius: 3 })
function addObj() {
  if (!newObj.value.name.trim()) return
  objects.value.push({ ...newObj.value })
  newObj.value = { name: '', kind: 'light', light_radius: 3 }
}
function kindLabel(k: string) {
  return { light: '光源', container: '容器', decor: '装饰' }[k] || k
}

// ---- Actor 库 ----
const actorFilter = ref('')
const showActorForm = ref(false)
const editingActor = ref<Actor | null>(null)
const actorForm = ref<ActorCreate>({
  name: '', type: 'monster', hp: 100, max_hp: 100, armor: 5,
  ap: 2, max_ap: 2, vision_range: 8, darkvision: 0,
  listen_radius: 6, passive_perception: 10, stealth: 0,
  is_shop: false, shop_items: [],
})

function toggleShopItem(name: string) {
  const list = actorForm.value.shop_items || (actorForm.value.shop_items = [])
  const idx = list.indexOf(name)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(name)
}

const dragActorId = ref<string | null>(null)

const filteredActors = computed(() => {
  if (!actorFilter.value) return actorStore.actors
  const q = actorFilter.value.toLowerCase()
  return actorStore.actors.filter(a => a.name.toLowerCase().includes(q))
})

function typeLabel(t: string) {
  return { player: '玩家', npc: 'NPC', monster: '怪物' }[t] || t
}

function newActor() {
  editingActor.value = null
  actorForm.value = {
    name: '', type: 'monster', hp: 100, max_hp: 100, armor: 5,
    ap: 2, max_ap: 2, vision_range: 8, darkvision: 0,
    listen_radius: 6, passive_perception: 10, stealth: 0,
    is_shop: false, shop_items: [],
  }
  showActorForm.value = true
}

function editActor(a: Actor) {
  editingActor.value = a
  actorForm.value = { name: a.name, type: a.type as any, avatar_url: a.avatar_url, hp: a.hp, max_hp: a.max_hp, armor: a.armor, ap: a.ap, max_ap: a.max_ap, vision_range: a.vision_range, darkvision: a.darkvision, listen_radius: a.listen_radius, passive_perception: a.passive_perception, stealth: a.stealth, is_shop: a.is_shop, shop_items: [...(a.shop_items || [])] }
  showActorForm.value = true
}

async function saveActor() {
  if (!actorForm.value.name.trim()) return
  if (editingActor.value) {
    await actorStore.update(editingActor.value.id, actorForm.value)
  } else {
    await actorStore.create(actorForm.value)
  }
  showActorForm.value = false
  editingActor.value = null
}

async function duplicateActor(a: Actor) {
  await actorStore.create({ ...a, name: a.name + '_副本' })
}

async function deleteActor(id: string) {
  await actorStore.remove(id)
}

function onActorDragStart(e: DragEvent, a: Actor) {
  dragActorId.value = a.id
  e.dataTransfer?.setData('application/json', JSON.stringify({
    kind: 'actor', actor_id: a.id, name: a.name,
  }))
  e.dataTransfer!.effectAllowed = 'copy'
  const el = e.target as HTMLElement
  if (el) {
    e.dataTransfer?.setDragImage(el, 10, 10)
  }
}

async function onAvatarUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    actorForm.value.avatar_url = await uploadAvatar(file)
  } catch (err) {
    alert('头像上传失败: ' + (err as Error).message)
  } finally {
    input.value = ''
  }
}

// ---- 道具库 ----
const itemFilter = ref('')
const showItemForm = ref(false)
const editingItem = ref<Item | null>(null)
const emptyItemForm = (): ItemCreate => ({
  name: '', category: 'misc', description: '', effect_text: '', price: 0, icon_url: '',
})
const itemForm = ref<ItemCreate>(emptyItemForm())

const filteredItems = computed(() => {
  if (!itemFilter.value) return itemStore.items
  const q = itemFilter.value.toLowerCase()
  return itemStore.items.filter(i => i.name.toLowerCase().includes(q))
})

function categoryLabel(c: string) {
  return { weapon: '武器', armor: '护甲', consumable: '消耗品', skill: '技能', misc: '杂项' }[c] || c
}

function newItem() {
  editingItem.value = null
  itemForm.value = emptyItemForm()
  showItemForm.value = true
}

function editItem(i: Item) {
  editingItem.value = i
  itemForm.value = {
    name: i.name, category: i.category, description: i.description,
    effect_text: i.effect_text, price: i.price, icon_url: i.icon_url,
  }
  showItemForm.value = true
}

async function saveItem() {
  if (!itemForm.value.name.trim()) return
  if (editingItem.value) {
    await itemStore.update(editingItem.value.id, itemForm.value)
  } else {
    await itemStore.create(itemForm.value)
  }
  showItemForm.value = false
  editingItem.value = null
}

async function deleteItem(id: string) {
  await itemStore.remove(id)
}

// ---- 内容库（事件/陷阱/怪物/奇遇/NPC，所有人只读参考）----
const libCats = [
  { key: 'event', label: '事件' },
  { key: 'trap', label: '陷阱' },
  { key: 'monster', label: '怪物' },
  { key: 'adventure', label: '奇遇' },
  { key: 'npc', label: 'NPC' },
]
const libEntries = ref<LibraryEntry[]>([])
const libCategory = ref('event')
const libFilter = ref('')
const libLoading = ref(false)
const expandedLib = ref<string | null>(null)
async function loadLibrary() {
  libLoading.value = true
  try { libEntries.value = await listLibrary() }
  catch (e) { console.warn(e) }
  finally { libLoading.value = false }
}
function toggleLib(id: string) {
  expandedLib.value = expandedLib.value === id ? null : id
}
const filteredLibrary = computed(() => {
  const q = libFilter.value.trim().toLowerCase()
  return libEntries.value.filter((e) =>
    e.category === libCategory.value &&
    (!q || e.name.toLowerCase().includes(q) || e.effect_text.toLowerCase().includes(q)))
})

// 导出：把当前内容库存成 JSON 文件（即"规范格式"，AI 照此整理 Excel 即可一键导入）
function exportLibrary() {
  const blob = new Blob([JSON.stringify(libEntries.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `library_export_${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
}
// 导入：上传 JSON 数组（与导出同格式，id 可省略），按 id upsert 并持久化
const libImporting = ref(false)
async function onImportLibrary(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  libImporting.value = true
  try {
    const data = JSON.parse(await file.text())
    const entries = Array.isArray(data) ? data : data.entries
    if (!Array.isArray(entries)) throw new Error('文件应是条目数组（或 {entries:[...]}）')
    const res = await importLibrary(entries, 'upsert')
    await loadLibrary()
    pushToast(`导入成功：新增 ${res.added ?? 0} · 更新 ${res.updated ?? 0} · 共 ${res.total}`, 'info')
  } catch (err) {
    pushToast('导入失败：' + (err as Error).message, 'error')
  } finally {
    libImporting.value = false
    input.value = ''
  }
}

// ---- 抽取表（所有人可抽；增删改仅管理员）----
const rollTables = ref<RollTable[]>([])
const lastDraw = ref<DrawResult | null>(null)
async function loadRollTables() {
  try { rollTables.value = await listRollTables() } catch (e) { console.warn(e) }
}
async function doDraw(t: RollTable) {
  // 管理员在对局内：服务端抽取并广播到战斗频道（全房间可见）
  if (props.inBattle && canManageLibrary.value) {
    window.dispatchEvent(new CustomEvent('ws-send', { detail: { type: 'draw_table', payload: { table_id: t.id } } }))
    pushToast(`🎲 已抽取「${t.name}」，结果广播到战斗频道`, 'info')
    return
  }
  // 其余（待机态预览 / 非管理员）：本地 REST 抽取，只自己看
  try {
    lastDraw.value = await drawRollTable(t.id)
    pushToast(`🎲 ${lastDraw.value.table_name}：${lastDraw.value.text}`, 'info')
  } catch { pushToast('抽取失败', 'error') }
}
function rtCatLabel(c: string) {
  return ({ event: '事件', trap: '陷阱', monster: '怪物', adventure: '奇遇', npc: 'NPC' } as Record<string, string>)[c] || c
}
const showTableForm = ref(false)
const editingTable = ref<RollTable | null>(null)
const emptyTableForm = () => ({ name: '', description: '', source_category: '' as RollTable['source_category'], entries: [{ weight: 1, text: '' }] })
const tableForm = ref(emptyTableForm())
function newTable() { editingTable.value = null; tableForm.value = emptyTableForm(); showTableForm.value = true }
function editTable(t: RollTable) {
  editingTable.value = t
  tableForm.value = { name: t.name, description: t.description, source_category: t.source_category,
    entries: t.entries.length ? t.entries.map((e) => ({ weight: e.weight, text: e.text })) : [{ weight: 1, text: '' }] }
  showTableForm.value = true
}
async function saveTable() {
  if (!tableForm.value.name.trim()) return
  const f = tableForm.value
  const body = { name: f.name, description: f.description, source_category: f.source_category,
    entries: f.source_category ? [] : f.entries.filter((e) => e.text.trim()) }
  try {
    if (editingTable.value) await updateRollTable(editingTable.value.id, body)
    else await createRollTable(body)
    showTableForm.value = false
    await loadRollTables()
  } catch (e) { pushToast('保存失败：' + (e as Error).message, 'error') }
}
async function removeTable(t: RollTable) {
  if (!confirm(`删除抽取表「${t.name}」？`)) return
  try { await deleteRollTable(t.id); await loadRollTables() } catch { pushToast('删除失败', 'error') }
}

// 角色卡保存/新建/删除后（CharacterSheetEditor 派发）刷新「我的角色卡」列表
function onSheetsChanged() { loadMySheets() }

onMounted(() => {
  loadMySheets()
  loadLibrary()
  loadRollTables()
  if (canViewAllSheets.value) loadSheets()  // /admin/characters 仅管理员；玩家跳过避免 401
  actorStore.load()
  itemStore.load()
  window.addEventListener('sheets-changed', onSheetsChanged)
})
onUnmounted(() => window.removeEventListener('sheets-changed', onSheetsChanged))
</script>

<style scoped>
/* 自适应宽度：在导航弹窗里能撑开，在战役态 300px 资源库侧栏里也不溢出 */
.res-mgr { min-width: 0; width: 100%; font-size: 13px; }
.tabs { flex-wrap: wrap; }
.tabs { display: flex; border-bottom: 1px solid #ddd; margin-bottom: 8px; }
.tabs button { flex: 1; padding: 6px; border: none; background: transparent;
  cursor: pointer; font-size: 12px; border-bottom: 2px solid transparent; }
.tabs button.active { border-bottom-color: #fa0; font-weight: bold; }
.panel { max-height: 60vh; overflow-y: auto; }
.loading, .empty { color: #999; padding: 16px; text-align: center; }
.sheet-list, .tmpl-list { list-style: none; padding: 0; margin: 0; }
.sheet-list li, .tmpl-list li { padding: 8px; border: 1px solid #eee;
  border-radius: 4px; margin-bottom: 6px; cursor: pointer; }
.sheet-list li:hover, .tmpl-list li:hover { background: #f8f8ff; }
.row-head { display: flex; align-items: center; gap: 8px; }
.meta { color: #666; font-size: 11px; }
.badge { background: #609; color: #fff; padding: 1px 5px; border-radius: 8px;
  font-size: 10px; }
.detail { margin-top: 8px; padding-top: 8px; border-top: 1px dashed #ddd; }
.kv { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 11px; color: #444;
  margin-bottom: 6px; }
.slots h6 { margin: 6px 0 3px; font-size: 11px; color: #fa0; }
.chip { display: inline-block; background: #eef; border: 1px solid #ccd;
  padding: 2px 6px; border-radius: 10px; font-size: 11px; margin: 2px; }
.secret { margin-top: 6px; padding: 6px; background: #fff8e0;
  border: 1px dashed #da6; border-radius: 3px; }
.secret h6 { margin: 0 0 4px; color: #c80; font-size: 11px; }
.secret p { margin: 2px 0; font-size: 11px; color: #553; }
.add-form { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px;
  padding-bottom: 8px; border-bottom: 1px dashed #eee; }
.add-form input, .add-form select { padding: 4px; font-size: 12px;
  border: 1px solid #ccc; border-radius: 3px; min-width: 60px; }
.add-form button { padding: 4px 10px; background: #0f3460; color: #fff;
  border: none; border-radius: 3px; cursor: pointer; font-size: 12px; }
.mini-check { font-size: 11px; display: flex; align-items: center; gap: 2px; }
.mini-check input { width: auto; }
.shop-config { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #ddd; }
.shop-items-pick { margin-top: 6px; }
.shop-items-pick .hint { font-size: 11px; color: #888; margin: 0 0 6px; }
.chip.pick { cursor: pointer; }
.chip.pick.active { background: #0a7; border-color: #0a7; color: #fff; }
.chip-pool { display: flex; flex-wrap: wrap; gap: 4px; }
.chip.removable { cursor: pointer; background: #fee; border-color: #fcc; }
.chip.removable:hover { background: #fcc; }
.del { background: #c33; color: #fff; border: none; padding: 2px 6px;
  border-radius: 2px; cursor: pointer; font-size: 11px; margin-left: auto; }
/* Actor 库 */
.add-btn { background: #0a7; color: #fff; }
.search-input { flex: 1; }
.actor-list { list-style: none; padding: 0; margin: 0; }
.actor-card { display: flex; align-items: center; gap: 8px; padding: 6px;
  border: 1px solid #eee; border-radius: 4px; margin-bottom: 4px; cursor: grab; }
.actor-card:hover { background: #f0f8ff; border-color: #8af; }
.actor-avatar { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
.actor-avatar.placeholder { display: flex; align-items: center; justify-content: center;
  background: #dde; color: #448; font-weight: bold; font-size: 16px; }
.actor-info { flex: 1; min-width: 0; }
.actor-name { font-weight: bold; font-size: 13px; }
.actor-meta { font-size: 11px; color: #666; }
.actor-actions { display: flex; gap: 2px; }
.drag-hint { color: #ccc; font-size: 12px; margin-left: auto; cursor: grab; }
/* 内容库 */
.lib-cats { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.lib-cats button { padding: 3px 10px; border: 1px solid #ccc; background: #fff;
  border-radius: 12px; cursor: pointer; font-size: 12px; }
.lib-cats button.active { background: #0f3460; color: #fff; border-color: #0f3460; }
.lib-list .meta { display: block; margin-top: 2px; white-space: normal; }
.kv b { color: #666; font-weight: 600; }
.lib-note { margin: 4px 0 0; font-size: 11px; color: #888; }
.lib-io { padding: 4px 8px; font-size: 12px; background: #0f3460; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; white-space: nowrap; }
.lib-io:disabled { background: #ccc; cursor: not-allowed; }
.lib-io.import { background: #0a7; display: inline-flex; align-items: center; }
.lib-count { font-size: 11px; color: #999; align-self: center; margin-left: auto; }
/* 抽取表 */
.draw-result { background: #fff8e0; border: 1px solid #f0c040; border-radius: 6px;
  padding: 8px 10px; margin-bottom: 8px; font-size: 13px; }
.draw-text { font-weight: 700; color: #c60; }
.draw-eff { margin-top: 4px; font-size: 12px; color: #666; }
.draw-btn { background: #fa0; color: #1a1a2e; border-color: #fa0; font-weight: 600; }
.rt-entries { margin-top: 10px; padding-top: 10px; border-top: 1px dashed #ddd; }
.rt-entries .hint { font-size: 11px; color: #888; margin: 0 0 6px; }
.rt-entry-row { display: flex; gap: 6px; margin-bottom: 4px; align-items: center; }
.rt-weight { width: 56px; padding: 4px; border: 1px solid #ccc; border-radius: 3px; }
.rt-text { flex: 1; padding: 4px; border: 1px solid #ccc; border-radius: 3px; }
.actor-card.dragging { opacity: 0.6; background: #e8f0ff; box-shadow: 0 0 0 2px #0f3460; }
.mini-btn { padding: 2px 6px; border: 1px solid #ccc; background: #fff;
  border-radius: 2px; cursor: pointer; font-size: 11px; }
.mini-btn.danger { background: #fee; border-color: #fcc; color: #c33; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 999; }
.modal-box { background: #fff; border-radius: 8px; padding: 20px; min-width: 400px;
  max-width: 90vw; max-height: 90vh; overflow-y: auto; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-grid label { display: flex; flex-direction: column; font-size: 12px; gap: 2px; }
.form-grid input, .form-grid select { padding: 4px; border: 1px solid #ccc; border-radius: 3px; }
.avatar-upload input[type="file"] { padding: 4px; font-size: 12px; }
.avatar-preview { margin: 4px 0; }
.avatar-preview img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; }
.form-actions { display: flex; gap: 8px; margin-top: 12px; justify-content: flex-end; }
.save-btn { background: #0a7; color: #fff; padding: 6px 14px; border: none; border-radius: 3px; cursor: pointer; }
.cancel-btn { background: #eee; padding: 6px 14px; border: 1px solid #ccc; border-radius: 3px; cursor: pointer; }
.modal-box h3 { margin: 0 0 12px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.form-grid label { display: flex; flex-direction: column; font-size: 11px; color: #666; }
.form-grid input, .form-grid select { margin-top: 2px; padding: 4px;
  border: 1px solid #ccc; border-radius: 3px; }
.form-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
.save-btn { background: #0a7; color: #fff; border: none; padding: 6px 16px;
  border-radius: 3px; cursor: pointer; }
.cancel-btn { background: #eee; color: #333; border: none; padding: 6px 16px;
  border-radius: 3px; cursor: pointer; }
</style>
