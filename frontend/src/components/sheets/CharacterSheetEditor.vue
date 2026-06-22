<template>
  <div class="sheet-editor">
    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <ul class="sheet-list">
        <li v-for="s in sheets" :key="s.id" :class="{ active: editing?.id === s.id }"
            @click="startEdit(s)">
          <span>{{ s.name || '(未命名)' }}</span>
          <button class="del" @click.stop="onDelete(s)">删</button>
        </li>
        <li class="new" @click="startNew">+ 新建角色卡</li>
      </ul>

      <div v-if="editing" class="form">
        <h4>{{ editing.id ? '编辑' : '新建' }}角色卡</h4>

        <!-- 基本信息 -->
        <section class="block">
          <h5>基本信息</h5>
          <input v-model="editing.name" placeholder="角色名称" />
          <div class="grid2">
            <input v-model="editing.nickname" placeholder="玩家昵称" />
            <input v-model="editing.gender" placeholder="性别" />
            <input v-model="editing.profession" placeholder="职业" />
            <input v-model="editing.talent" placeholder="天赋/血脉" />
          </div>
        </section>

        <!-- 基础属性 -->
        <section class="block">
          <h5>基础属性 <span class="cp-hint">(创造点上限 30，已用 {{ usedCP }}，剩余 {{ 30 - usedCP }})</span></h5>
          <div class="grid-nums">
            <label>生命<input type="number" v-model.number="editing.hp_base" /></label>
            <label>护甲<input type="number" v-model.number="editing.armor_base" /></label>
            <label>行动点<input type="number" v-model.number="editing.ap_base" /></label>
            <label>起始金币<input type="number" v-model.number="editing.gold" /></label>
          </div>
        </section>

        <!-- 装备栏 -->
        <section class="block">
          <h5>装备栏 <span class="cp-hint">(6格 + 2技能槽 + 1外挂)</span></h5>
          <div class="equip-grid">
            <label class="slot" v-for="(slot, i) in EQUIP_SLOTS" :key="slot.key">
              <span class="slot-name">{{ slot.label }}</span>
              <input v-model="editing.equipment_slots[i]" :placeholder="slot.placeholder" />
            </label>
            <label class="slot" v-for="(slot, i) in SKILL_SLOTS" :key="slot.key">
              <span class="slot-name">{{ slot.label }}</span>
              <input v-model="editing.skill_slots[i]" :placeholder="slot.placeholder" />
            </label>
            <label class="slot">
              <span class="slot-name">外挂</span>
              <input v-model="editing.externals_str" placeholder="外挂名称" />
            </label>
          </div>
        </section>

        <!-- 道具背包 -->
        <section class="block">
          <h5>道具背包 <span class="cp-hint">(战场获得/购买/拾取)</span></h5>
          <div class="backpack-grid">
            <input v-for="i in 6" :key="i"
                   v-model="editing.backpack[i - 1]"
                   :placeholder="`道具${i}`" />
          </div>
        </section>

        <!-- 底牌 -->
        <section class="block">
          <h5>底牌 <span class="cp-hint">(仅自己/管理员可见)</span></h5>
          <textarea v-model="editing.secrets_str" rows="2"
                    placeholder="底牌内容，私密信息..."></textarea>
        </section>

        <p v-if="error" class="err">{{ error }}</p>
        <p v-if="saved" class="ok">已保存</p>
        <div class="form-actions">
          <button @click="onSave">保存</button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { listMyCharacters, createCharacter, updateCharacter, deleteCharacter } from '../../api/rest'
import type { CharacterSheet } from '../../api/types'

interface EditingSheet {
  id?: string
  name: string
  nickname: string
  gender: string
  profession: string
  talent: string
  hp_base: number
  armor_base: number
  ap_base: number
  gold: number
  equipment_slots: string[]
  skill_slots: string[]
  externals_str: string
  backpack: string[]
  secrets_str: string
}

const EQUIP_SLOTS = [
  { key: 'main_weapon', label: '主武器', placeholder: '武器名称' },
  { key: 'sub_weapon', label: '副武器', placeholder: '武器名称' },
  { key: 'armor', label: '护甲', placeholder: '护甲名称' },
  { key: 'accessory1', label: '饰品1', placeholder: '饰品名称' },
  { key: 'accessory2', label: '饰品2', placeholder: '饰品名称' },
  { key: 'accessory3', label: '饰品3', placeholder: '饰品名称' },
]
const SKILL_SLOTS = [
  { key: 'skill1', label: '技能1', placeholder: '技能名称' },
  { key: 'skill2', label: '技能2', placeholder: '技能名称' },
]

const sheets = ref<CharacterSheet[]>([])
const editing = ref<EditingSheet | null>(null)
const loading = ref(true)
const error = ref('')
const saved = ref(false)

// Simple creation-point estimate (configurable later)
const usedCP = computed(() => {
  if (!editing.value) return 0
  const e = editing.value
  return Math.max(0, (e.hp_base - 100) / 10 + (e.armor_base - 5) + (e.ap_base - 2) * 5)
})

async function load() {
  loading.value = true
  try { sheets.value = await listMyCharacters() } finally { loading.value = false }
}

function emptySheet(): EditingSheet {
  return {
    name: '', nickname: '', gender: '', profession: '', talent: '',
    hp_base: 100, armor_base: 5, ap_base: 2, gold: 0,
    equipment_slots: ['', '', '', '', '', ''],
    skill_slots: ['', ''],
    externals_str: '',
    backpack: ['', '', '', '', '', ''],
    secrets_str: '',
  }
}

function startEdit(s: CharacterSheet) {
  editing.value = {
    id: s.id,
    name: s.name || '',
    nickname: '',
    gender: s.gender || '',
    profession: s.profession || '',
    talent: s.talent || '',
    hp_base: s.hp_base ?? 100,
    armor_base: s.armor_base ?? 5,
    ap_base: s.ap_base ?? 2,
    gold: s.gold ?? 0,
    // null → '' for text input binding
    equipment_slots: (s.equipment_slots || []).map((x) => x ?? ''),
    skill_slots: (s.skill_slots || []).map((x) => x ?? ''),
    externals_str: '',
    backpack: [...(s.backpack || []), '', '', '', '', '', ''].slice(0, 6),
    secrets_str: (s.secret_backups || []).join(', '),
  }
  error.value = ''; saved.value = false
}

function startNew() {
  editing.value = emptySheet()
  error.value = ''; saved.value = false
}

async function onSave() {
  if (!editing.value) return
  error.value = ''; saved.value = false
  const e = editing.value
  if (!e.name.trim()) { error.value = '请填写角色名称'; return }

  // Pad arrays to expected sizes
  const equipment = [...e.equipment_slots]
  while (equipment.length < 6) equipment.push('')
  const skills = [...e.skill_slots]
  while (skills.length < 2) skills.push('')
  const backpack = [...e.backpack]
  while (backpack.length < 6) backpack.push('')
  // Merge externals into backpack tail or store as part of equipment_slots later
  // For MVP, externals is stored as 7th equipment slot via backpack convention.
  // Simpler: we append externals as a tagged string in backpack if non-empty.
  const finalBackpack = backpack.filter((s) => s.trim())
  if (e.externals_str.trim()) {
    finalBackpack.push(`[外挂]${e.externals_str.trim()}`)
  }

  const body = {
    name: e.name,
    gender: e.gender,
    profession: e.profession,
    talent: e.talent,
    hp_base: e.hp_base,
    armor_base: e.armor_base,
    ap_base: e.ap_base,
    gold: e.gold,
    backpack: finalBackpack,
    equipment_slots: equipment.map((s) => s.trim() || null),
    skill_slots: skills.map((s) => s.trim() || null),
    secret_backups: e.secrets_str.split(',').map((s) => s.trim()).filter(Boolean),
  }
  try {
    if (e.id) {
      await updateCharacter(e.id, body)
    } else {
      await createCharacter(body)
    }
    saved.value = true
    await load()
  } catch (err: any) {
    error.value = err.message || '保存失败'
  }
}

async function onDelete(s: CharacterSheet) {
  if (!confirm(`确定删除角色卡「${s.name}」？`)) return
  try {
    await deleteCharacter(s.id)
    await load()
    if (editing.value?.id === s.id) editing.value = null
  } catch (err: any) {
    error.value = err.message
  }
}

onMounted(load)
</script>

<style scoped>
.sheet-editor { display: flex; gap: 16px; min-height: 360px; font-size: 13px; }
.sheet-list { list-style: none; padding: 0; margin: 0; min-width: 180px;
  border-right: 1px solid #eee; padding-right: 12px; }
.sheet-list li { padding: 6px 8px; cursor: pointer; display: flex;
  justify-content: space-between; align-items: center; border-radius: 3px; }
.sheet-list li:hover { background: #f0f0f0; }
.sheet-list li.active { background: #e0f0ff; }
.sheet-list li.new { color: #0f3460; font-weight: bold; }
.del { background: #c33; color: #fff; border: none; padding: 2px 6px;
  border-radius: 2px; cursor: pointer; font-size: 11px; }
.form { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.form h4 { margin: 0 0 4px; font-size: 15px; }
.block { border: 1px solid #eee; border-radius: 4px; padding: 10px; background: #fafafa; }
.block h5 { margin: 0 0 8px; font-size: 13px; color: #0f3460;
  border-bottom: 1px dashed #ccc; padding-bottom: 4px; }
.cp-hint { font-size: 11px; color: #888; font-weight: normal; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.grid-nums { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.grid-nums label { display: flex; flex-direction: column; font-size: 11px; color: #666; }
.equip-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.slot { display: flex; flex-direction: column; font-size: 11px; }
.slot-name { color: #0f3460; font-weight: 500; margin-bottom: 2px; }
.backpack-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
textarea { font-family: inherit; resize: vertical; }
.form-actions { display: flex; justify-content: flex-end; }
.err { color: #c33; margin: 0; } .ok { color: #3a7; margin: 0; }

/* Override global input style from Modal: use scoped explicit rules */
.sheet-editor input, .sheet-editor textarea {
  padding: 5px 8px; border: 1px solid #ccc; border-radius: 3px;
  font-size: 12px; width: 100%; box-sizing: border-box; margin: 0;
}
.sheet-editor input:focus, .sheet-editor textarea:focus {
  outline: none; border-color: #0f3460;
}
</style>
