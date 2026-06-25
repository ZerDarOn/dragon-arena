<template>
  <div class="mini-res-panel">
    <div class="mini-header">
      <span class="title">📚 资源库</span>
      <button class="close" @click="$emit('close')">×</button>
    </div>
    <div class="mini-tabs">
      <button v-for="t in tabs" :key="t.key" @click="active = t.key"
              :class="{ active: active === t.key }">{{ t.label }}</button>
    </div>
    <div class="mini-list">
      <!-- Actor 角色模板 -->
      <template v-if="active === 'actors'">
        <div v-if="actorStore.actors.length === 0" class="empty">暂无角色模板</div>
        <div v-for="a in filteredActors" :key="a.id" class="mini-card"
             :class="{ dragging: dragId === a.id }"
             draggable="true"
             @dragstart="onDragStart($event, a)"
             @dragend="dragId = null"
             @click="editActor(a)"
             :title="`拖拽「${a.name}」到地图`">
          <img v-if="a.avatar_url" :src="a.avatar_url" class="avatar" />
          <div v-else class="avatar">{{ a.name[0] || '?' }}</div>
          <div class="info">
            <div class="name">{{ a.name }}</div>
            <div class="meta">{{ typeLabel(a.type) }} · HP{{ a.hp }}/{{ a.max_hp }} · 甲{{ a.armor }}</div>
          </div>
          <div class="drag-hint">⋮⋮</div>
        </div>
      </template>

      <!-- 怪物模板 -->
      <template v-if="active === 'monsters'">
        <div v-if="monsters.length === 0" class="empty">暂无怪物模板</div>
        <div v-for="(m, i) in monsters" :key="i" class="mini-card"
             draggable="true"
             @dragstart="onMonsterDragStart($event, m)"
             :title="`拖拽「${m.name}」到地图`">
          <div class="avatar monster">{{ m.name[0] || '?' }}</div>
          <div class="info">
            <div class="name">{{ m.name }}</div>
            <div class="meta">HP{{ m.hp }} · 甲{{ m.armor }} · 视{{ m.vision_range }}</div>
          </div>
        </div>
      </template>

      <!-- 装备池 -->
      <template v-if="active === 'equip'">
        <div v-if="equips.length === 0" class="empty">暂无装备</div>
        <div v-for="(e, i) in equips" :key="i" class="chip">{{ e }}</div>
      </template>
    </div>

    <!-- Actor 编辑弹窗 -->
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
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useActorStore } from '../../stores/actors'
import type { Actor, ActorCreate } from '../../api/types'

const actorStore = useActorStore()
const active = ref('actors')
const dragId = ref<string | null>(null)
const showActorForm = ref(false)
const editingActor = ref<Actor | null>(null)
const actorFilter = ref('')

const tabs = [
  { key: 'actors', label: '角色' },
  { key: 'monsters', label: '怪物' },
  { key: 'equip', label: '装备' },
]

const actorForm = ref<ActorCreate>({
  name: '', type: 'npc', hp: 100, max_hp: 100, armor: 5, ap: 2, max_ap: 2,
  vision_range: 8, darkvision: 0, listen_radius: 10, passive_perception: 10, stealth: 0,
  avatar_url: '',
})

const filteredActors = computed(() => {
  const list = actorStore.actors
  if (!actorFilter.value) return list
  const q = actorFilter.value.toLowerCase()
  return list.filter((a) => a.name.toLowerCase().includes(q))
})

function typeLabel(t: string) {
  return { player: '玩家', npc: 'NPC', monster: '怪物' }[t] || t
}

function onDragStart(e: DragEvent, a: Actor) {
  dragId.value = a.id
  e.dataTransfer?.setData('application/json', JSON.stringify({
    kind: 'actor', actor_id: a.id, name: a.name,
  }))
  e.dataTransfer!.effectAllowed = 'copy'
}

function onMonsterDragStart(e: DragEvent, m: any) {
  e.dataTransfer?.setData('application/json', JSON.stringify({
    kind: 'actor', actor_id: `monster_${m.name}`, name: m.name,
    hp: m.hp, armor: m.armor, vision_range: m.vision_range, darkvision: m.darkvision,
  }))
  e.dataTransfer!.effectAllowed = 'copy'
}

function editActor(a: Actor) {
  editingActor.value = a
  actorForm.value = { ...a }
  showActorForm.value = true
}

async function saveActor() {
  if (editingActor.value) {
    await actorStore.update(editingActor.value.id, actorForm.value)
  } else {
    await actorStore.create(actorForm.value)
  }
  showActorForm.value = false
  editingActor.value = null
}

async function onAvatarUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  try {
    const r = await fetch(`http://${window.location.hostname}:8000/api/upload/avatar`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('dragon_arena_token') || ''}` },
      body: form,
    })
    if (!r.ok) throw new Error('上传失败')
    const data = await r.json()
    actorForm.value.avatar_url = `http://${window.location.hostname}:8000${data.url}`
  } catch (err) {
    alert('头像上传失败: ' + (err as Error).message)
  } finally {
    input.value = ''
  }
}

// 本地存储的怪物/装备
const monsters = ref<any[]>([])
const equips = ref<string[]>([])

onMounted(() => {
  actorStore.load()
  const saved = localStorage.getItem('res_monsters')
  if (saved) monsters.value = JSON.parse(saved)
  const savedEq = localStorage.getItem('res_equips')
  if (savedEq) equips.value = JSON.parse(savedEq)
})

defineEmits<{
  (e: 'close'): void
}>()
</script>

<style scoped>
.mini-res-panel { display: flex; flex-direction: column; height: 100%; background: #f8f9fa; }
.mini-header { display: flex; justify-content: space-between; align-items: center;
  padding: 6px 10px; background: #0f3460; color: #fff; }
.mini-header .title { font-size: 13px; font-weight: 600; }
.mini-header .close { background: none; border: none; color: #fff; font-size: 18px; cursor: pointer; }
.mini-tabs { display: flex; gap: 2px; padding: 4px; border-bottom: 1px solid #e0e0e0; }
.mini-tabs button { flex: 1; padding: 4px; border: none; background: #eee; cursor: pointer; font-size: 11px; border-radius: 3px; }
.mini-tabs button.active { background: #0f3460; color: #fff; }
.mini-list { flex: 1; overflow-y: auto; padding: 6px; }
.mini-card { display: flex; align-items: center; gap: 8px; padding: 8px;
  background: #fff; border-radius: 6px; margin-bottom: 6px; cursor: grab;
  border: 1px solid #e0e0e0; transition: all 0.15s; }
.mini-card:hover { border-color: #0f3460; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
.mini-card.dragging { opacity: 0.5; background: #e3f2fd; }
.avatar { width: 32px; height: 32px; border-radius: 50%; background: #0f3460;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 600; flex-shrink: 0; object-fit: cover; }
.avatar.monster { background: #c33; }
.info { flex: 1; min-width: 0; }
.name { font-size: 13px; font-weight: 600; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta { font-size: 11px; color: #888; margin-top: 1px; }
.drag-hint { color: #ccc; font-size: 12px; cursor: grab; }
.empty { text-align: center; padding: 20px; color: #999; font-size: 12px; }
.chip { display: inline-block; padding: 2px 8px; background: #e3f2fd; border-radius: 10px;
  font-size: 11px; margin: 2px; color: #0f3460; }

/* 弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 100;
  display: flex; align-items: center; justify-content: center; }
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
</style>
