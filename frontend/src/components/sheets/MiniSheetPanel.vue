<template>
  <div class="mini-sheet-panel">
    <div class="mini-header">
      <span class="title">🎭 角色卡</span>
      <button class="close" @click="$emit('close')">×</button>
    </div>
    <div class="mini-list">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="!sheets.length" class="empty">暂无角色卡</div>
      <div v-for="s in sheets" :key="s.id" class="mini-card"
           :class="{ dragging: dragId === s.id }"
           draggable="true"
           @dragstart="onDragStart($event, s)"
           @dragend="dragId = null"
           @click="$emit('edit', s)"
           :title="`拖拽「${s.name}」到地图`">
        <div class="avatar">{{ s.name[0] || '?' }}</div>
        <div class="info">
          <div class="name">{{ s.name || '未命名' }}</div>
          <div class="meta">{{ s.profession }} · HP{{ s.hp_base }} · 甲{{ s.armor_base }}</div>
        </div>
        <div class="drag-hint">⋮⋮</div>
      </div>
    </div>
    <button class="add-btn" @click="$emit('create')">+ 新建</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listMyCharacters, listAllCharacters } from '../../api/rest'
import { useAuthStore } from '../../stores/auth'

const auth = useAuthStore()
const sheets = ref<CharacterSheet[]>([])
const loading = ref(true)
const dragId = ref<string | null>(null)

async function load() {
  loading.value = true
  try {
    sheets.value = auth.isAdmin
      ? await listAllCharacters()
      : await listMyCharacters()
  } catch {
    sheets.value = []
  } finally {
    loading.value = false
  }
}

function onDragStart(e: DragEvent, s: CharacterSheet) {
  dragId.value = s.id
  e.dataTransfer?.setData('application/json', JSON.stringify({
    kind: 'character_sheet', sheet_id: s.id, name: s.name,
  }))
  e.dataTransfer!.effectAllowed = 'copy'
}

onMounted(load)

defineEmits<{
  (e: 'close'): void
  (e: 'edit', sheet: CharacterSheet): void
  (e: 'create'): void
}>()
</script>

<style scoped>
.mini-sheet-panel { display: flex; flex-direction: column; height: 100%; background: #f8f9fa; }
.mini-header { display: flex; justify-content: space-between; align-items: center;
  padding: 6px 10px; background: #3a7; color: #fff; }
.mini-header .title { font-size: 13px; font-weight: 600; }
.mini-header .close { background: none; border: none; color: #fff; font-size: 18px; cursor: pointer; }
.mini-list { flex: 1; overflow-y: auto; padding: 6px; }
.mini-card { display: flex; align-items: center; gap: 8px; padding: 8px;
  background: #fff; border-radius: 6px; margin-bottom: 6px; cursor: grab;
  border: 1px solid #e0e0e0; transition: all 0.15s; }
.mini-card:hover { border-color: #3a7; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
.mini-card.dragging { opacity: 0.5; background: #e8f5e9; }
.avatar { width: 32px; height: 32px; border-radius: 50%; background: #3a7;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 600; flex-shrink: 0; }
.info { flex: 1; min-width: 0; }
.name { font-size: 13px; font-weight: 600; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meta { font-size: 11px; color: #888; margin-top: 1px; }
.drag-hint { color: #ccc; font-size: 12px; cursor: grab; }
.add-btn { margin: 6px; padding: 8px; background: #fff; border: 1px dashed #3a7;
  color: #3a7; border-radius: 6px; cursor: pointer; font-size: 12px; }
.add-btn:hover { background: #e8f5e9; }
.loading, .empty { text-align: center; padding: 20px; color: #999; font-size: 12px; }
</style>
