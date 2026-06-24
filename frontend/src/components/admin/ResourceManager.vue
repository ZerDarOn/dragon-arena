<template>
  <div class="res-mgr">
    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" @click="active = t.key"
              :class="{ active: active === t.key }">{{ t.label }}</button>
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
      <div class="add-form">
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
          <button class="del" @click="monsters.splice(i, 1)">删</button>
        </li>
        <li v-if="!monsters.length" class="empty">暂无怪物模板</li>
      </ul>
    </div>

    <!-- 装备池 -->
    <div v-if="active === 'equip'" class="panel">
      <div class="add-form">
        <input v-model="newEquip" placeholder="装备/外挂名称" @keyup.enter="addEquip" />
        <button @click="addEquip">添加</button>
      </div>
      <div class="chip-pool">
        <span v-for="(e, i) in equips" :key="i" class="chip removable" @click="equips.splice(i, 1)">
          {{ e }} ✕
        </span>
        <span v-if="!equips.length" class="empty">暂无装备</span>
      </div>
    </div>

    <!-- 角色卡模板（Actor 库）-->
    <div v-if="active === 'actors'" class="panel">
      <div class="add-form">
        <button @click="showActorForm = true" class="add-btn">+ 新建角色</button>
        <input v-model="actorFilter" placeholder="搜索..." class="search-input" />
      </div>
      <div v-if="actorStore.actors.length === 0" class="empty">暂无角色卡模板<br/><small>新建后可拖拽到地图生成 Token</small></div>
      <ul class="actor-list">
        <li v-for="a in filteredActors" :key="a.id" class="actor-card"
            :class="{ dragging: dragActorId === a.id }"
            draggable="true" @dragstart="onActorDragStart($event, a)" @dragend="dragActorId = null"
            @click="editActor(a)"
            :title="`拖拽「${a.name}」到地图投放`">
          <img v-if="a.avatar_url" :src="a.avatar_url" class="actor-avatar" />
          <div v-else class="actor-avatar placeholder">{{ a.name[0] }}</div>
          <div class="actor-info">
            <div class="actor-name">{{ a.name }}</div>
            <div class="actor-meta">{{ typeLabel(a.type) }} · HP{{ a.hp }}/{{ a.max_hp }} · 甲{{ a.armor }}</div>
          </div>
          <div class="actor-actions">
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
          <div class="form-actions">
            <button @click="saveActor" class="save-btn">保存</button>
            <button @click="showActorForm = false" class="cancel-btn">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 光源/物件模板 -->
    <div v-if="active === 'objects'" class="panel">
      <div class="add-form">
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
          <button class="del" @click="objects.splice(i, 1)">删</button>
        </li>
        <li v-if="!objects.length" class="empty">暂无物件模板</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { listAllCharacters } from '../../api/rest'
import type { CharacterSheet, Actor, ActorCreate } from '../../api/types'
import { monsters, equips, objects } from '../../stores/resources'
import { useActorStore } from '../../stores/actors'

const actorStore = useActorStore()

const tabs = [
  { key: 'sheets', label: '角色卡库' },
  { key: 'actors', label: '角色模板' },
  { key: 'monsters', label: '怪物模板' },
  { key: 'equip', label: '装备池' },
  { key: 'objects', label: '物件' },
]
const active = ref('sheets')

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
})

const dragActorId = ref<string | null>(null)

const filteredActors = computed(() => {
  if (!actorFilter.value) return actorStore.actors
  const q = actorFilter.value.toLowerCase()
  return actorStore.actors.filter(a => a.name.toLowerCase().includes(q))
})

function typeLabel(t: string) {
  return { player: '玩家', npc: 'NPC', monster: '怪物' }[t] || t
}

function editActor(a: Actor) {
  editingActor.value = a
  actorForm.value = { name: a.name, type: a.type as any, avatar_url: a.avatar_url, hp: a.hp, max_hp: a.max_hp, armor: a.armor, ap: a.ap, max_ap: a.max_ap, vision_range: a.vision_range, darkvision: a.darkvision, listen_radius: a.listen_radius, passive_perception: a.passive_perception, stealth: a.stealth }
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
  const form = new FormData()
  form.append('file', file)
  try {
    const r = await fetch('http://localhost:8000/api/upload/avatar', {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
      body: form,
    })
    if (!r.ok) throw new Error('上传失败')
    const data = await r.json()
    actorForm.value.avatar_url = data.url
  } catch (err) {
    alert('头像上传失败: ' + (err as Error).message)
  } finally {
    input.value = ''
  }
}

onMounted(() => {
  loadSheets()
  actorStore.load()
})
</script>

<style scoped>
.res-mgr { min-width: 480px; font-size: 13px; }
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
