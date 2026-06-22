<template>
  <div class="sheet-editor">
    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <ul class="sheet-list">
        <li v-for="s in sheets" :key="s.id" :class="{ active: editing?.id === s.id }"
            @click="startEdit(s)">
          <span>{{ s.name }}</span>
          <button class="del" @click.stop="onDelete(s)">删</button>
        </li>
        <li class="new" @click="startNew">+ 新建角色卡</li>
      </ul>

      <div v-if="editing" class="form">
        <h4>{{ editing.id ? '编辑' : '新建' }}角色卡</h4>
        <input v-model="editing.name" placeholder="角色名" />
        <div class="row">
          <input v-model="editing.gender" placeholder="性别" />
          <input v-model="editing.profession" placeholder="职业" />
        </div>
        <input v-model="editing.talent" placeholder="天赋" />
        <div class="row nums">
          <label>HP<input type="number" v-model.number="editing.hp_base" /></label>
          <label>护甲<input type="number" v-model.number="editing.armor_base" /></label>
          <label>AP<input type="number" v-model.number="editing.ap_base" /></label>
          <label>金币<input type="number" v-model.number="editing.gold" /></label>
        </div>
        <textarea v-model="backpackStr" rows="2" placeholder="背包（逗号分隔）"></textarea>
        <textarea v-model="secretsStr" rows="2" placeholder="底牌（逗号分隔，仅自己/管理员可见）"></textarea>
        <p v-if="error" class="err">{{ error }}</p>
        <p v-if="saved" class="ok">已保存</p>
        <button @click="onSave">保存</button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { listMyCharacters, createCharacter, updateCharacter, deleteCharacter } from '../../api/rest'
import type { CharacterSheet } from '../../api/types'

const sheets = ref<CharacterSheet[]>([])
const editing = ref<any>(null)
const loading = ref(true)
const error = ref(''); const saved = ref(false)
const backpackStr = ref(''); const secretsStr = ref('')

async function load() {
  loading.value = true
  try { sheets.value = await listMyCharacters() } finally { loading.value = false }
}

function startEdit(s: CharacterSheet) {
  editing.value = { ...s }
  backpackStr.value = (s.backpack || []).join(', ')
  secretsStr.value = (s.secret_backups || []).join(', ')
  error.value = ''; saved.value = false
}

function startNew() {
  editing.value = {
    name: '', gender: '', profession: '', talent: '',
    hp_base: 100, armor_base: 5, ap_base: 2, gold: 0,
    backpack: [], secret_backups: [],
  }
  backpackStr.value = ''; secretsStr.value = ''
  error.value = ''; saved.value = false
}

async function onSave() {
  if (!editing.value) return
  error.value = ''; saved.value = false
  const body = {
    name: editing.value.name, gender: editing.value.gender,
    profession: editing.value.profession, talent: editing.value.talent,
    hp_base: editing.value.hp_base, armor_base: editing.value.armor_base,
    ap_base: editing.value.ap_base, gold: editing.value.gold,
    backpack: backpackStr.value.split(',').map((s: string) => s.trim()).filter(Boolean),
    equipment_slots: [null, null, null, null, null, null],
    skill_slots: [null, null],
    secret_backups: secretsStr.value.split(',').map((s: string) => s.trim()).filter(Boolean),
  }
  try {
    if (editing.value.id) {
      await updateCharacter(editing.value.id, body)
    } else {
      await createCharacter(body)
    }
    saved.value = true
    await load()
  } catch (e: any) {
    error.value = e.message
  }
}

async function onDelete(s: CharacterSheet) {
  if (!confirm(`确定删除角色卡「${s.name}」？`)) return
  try { await deleteCharacter(s.id); await load(); if (editing.value?.id === s.id) editing.value = null }
  catch (e: any) { error.value = e.message }
}

onMounted(load)
</script>

<style scoped>
.sheet-editor { display: flex; gap: 16px; min-height: 300px; font-size: 13px; }
.sheet-list { list-style: none; padding: 0; margin: 0; min-width: 160px; border-right: 1px solid #eee; padding-right: 12px; }
.sheet-list li { padding: 6px 8px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
.sheet-list li:hover { background: #f0f0f0; }
.sheet-list li.active { background: #e0f0ff; }
.sheet-list li.new { color: #0f3460; font-weight: bold; }
.del { background: #c33; color: #fff; border: none; padding: 2px 6px; border-radius: 2px; cursor: pointer; font-size: 11px; }
.form { flex: 1; }
.row { display: flex; gap: 8px; }
.row.nums label { flex: 1; display: flex; flex-direction: column; font-size: 11px; color: #666; }
textarea { font-family: inherit; }
.err { color: #c33; } .ok { color: #3a7; }
</style>
