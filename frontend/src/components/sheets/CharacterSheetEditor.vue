<template>
  <div class="sheet-editor">
    <div v-if="loading" class="loading">加载中...</div>
    <template v-else>
      <ul class="sheet-list">
        <li v-for="s in sheets" :key="s.id" :class="{ active: editing?.id === s.id, dragging: dragSheetId === s.id }"
            @click="startEdit(s)" draggable="true" @dragstart="onDragStart($event, s)" @dragend="dragSheetId = null"
            :title="`拖拽「${s.name}」到地图投放`">
          <span class="drag-handle">⋮⋮</span>
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
          <div class="avatar-row">
            <div class="avatar-preview">
              <img v-if="editing.avatar_url" :src="editing.avatar_url" alt="" />
              <span v-else>{{ editing.name[0] || '?' }}</span>
            </div>
            <label class="avatar-upload-btn">
              上传头像（用于地图棋子，方便区分）
              <input type="file" accept="image/*" hidden @change="onAvatarUpload" />
            </label>
            <button v-if="editing.avatar_url" class="avatar-clear" @click="editing.avatar_url = ''">移除</button>
          </div>
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
          <h5>基础属性 <span class="cp-hint" :class="{ 'cp-over': usedCP > 30 }">(创造点上限 30，已用 {{ usedCP }}，剩余 {{ 30 - usedCP }})</span></h5>
          <div class="grid-nums">
            <label>生命<input type="number" v-model.number="editing.hp_base" @change="clampCP('hp_base', 100, 10)" /></label>
            <label>护甲<input type="number" v-model.number="editing.armor_base" @change="clampCP('armor_base', 5, 1)" /></label>
            <label>行动点<input type="number" v-model.number="editing.ap_base" @change="clampCP('ap_base', 2, 5)" /></label>
            <label>起始金币<input type="number" v-model.number="editing.gold" /></label>
          </div>
        </section>

        <!-- 种族特性 / 感知 -->
        <section class="block">
          <h5>种族特性 / 感知 <span class="cp-hint">(影响战场视野与觉察)</span></h5>
          <label class="check-row">
            <input type="checkbox" v-model="editing.darkvision" />
            <span>黑暗视觉（黑暗格仍可见）</span>
          </label>
          <div class="grid-nums">
            <label>视野距离<input type="number" v-model.number="editing.vision_range" /></label>
            <label>被动觉察范围<input type="number" v-model.number="editing.listen_radius" /></label>
            <label>被动觉察值<input type="number" v-model.number="editing.passive_perception" /></label>
            <label>隐匿值<input type="number" v-model.number="editing.stealth" /></label>
          </div>
        </section>

        <!-- 装备栏 -->
        <section class="block">
          <h5>装备栏 <span class="cp-hint">(6格 + 2技能槽 + 1外挂)</span></h5>
          <div class="equip-grid">
            <label class="slot" v-for="(slot, i) in EQUIP_SLOTS" :key="slot.key">
              <span class="slot-name">{{ slot.label }}</span>
              <input v-model="editing.equipment_slots[i]" :placeholder="slot.placeholder"
                     list="equip-pool" />
            </label>
            <label class="slot" v-for="(slot, i) in SKILL_SLOTS" :key="slot.key">
              <span class="slot-name">{{ slot.label }}</span>
              <input v-model="editing.skill_slots[i]" :placeholder="slot.placeholder"
                     list="equip-pool" />
            </label>
            <label class="slot">
              <span class="slot-name">外挂</span>
              <input v-model="editing.externals_str" placeholder="外挂名称"
                     list="equip-pool" />
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
    <!-- 装备池 datalist（全局，供所有装备/技能/外挂输入框下拉） -->
    <datalist id="equip-pool">
      <option v-for="e in equips" :key="e" :value="e" />
    </datalist>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { listMyCharacters, createCharacter, updateCharacter, deleteCharacter, uploadAvatar } from '../../api/rest'
import type { CharacterSheet } from '../../api/types'
import { equips } from '../../stores/resources'

interface EditingSheet {
  id?: string
  name: string
  avatar_url: string
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
  darkvision: boolean
  vision_range: number
  listen_radius: number
  passive_perception: number
  stealth: number
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

const props = defineProps<{ initialSheetId?: string | null }>()

const sheets = ref<CharacterSheet[]>([])
const editing = ref<EditingSheet | null>(null)
const loading = ref(true)
const error = ref('')
const saved = ref(false)
const dragSheetId = ref<string | null>(null)
const uploading = ref(false)

// Simple creation-point estimate (configurable later)
const usedCP = computed(() => {
  if (!editing.value) return 0
  const e = editing.value
  return Math.max(0, (e.hp_base - 100) / 10 + (e.armor_base - 5) + (e.ap_base - 2) * 5)
})

// 输入级 CP 硬校验：如果当前值导致超限，自动回退到不超的最大值
function clampCP(field: 'hp_base' | 'armor_base' | 'ap_base', base: number, costPerUnit: number) {
  if (!editing.value) return
  const e = editing.value
  const val = e[field]
  if (val <= base) return // 低于基础值不收费，无需限制
  const currentCP = (e.hp_base - 100) / 10 + (e.armor_base - 5) + (e.ap_base - 2) * 5
  if (currentCP > 30) {
    const over = currentCP - 30
    const maxIncrease = Math.max(0, val - base - Math.ceil(over * costPerUnit) / costPerUnit)
    e[field] = Math.max(base, Math.floor(base + maxIncrease))
    error.value = `创造点上限 30，已用 ${usedCP.value}。${field === 'hp_base' ? '生命' : field === 'armor_base' ? '护甲' : '行动点'}已自动调整。`
  }
}

async function load() {
  loading.value = true
  try {
    sheets.value = await listMyCharacters()
    // 从外部点击某张卡片打开时，直接进入该卡片的编辑态，而不是空白/列表态
    if (props.initialSheetId) {
      const target = sheets.value.find((s) => s.id === props.initialSheetId)
      if (target) startEdit(target)
    }
  } finally { loading.value = false }
}

function emptySheet(): EditingSheet {
  return {
    name: '', avatar_url: '', nickname: '', gender: '', profession: '', talent: '',
    hp_base: 100, armor_base: 5, ap_base: 2, gold: 0,
    equipment_slots: ['', '', '', '', '', ''],
    skill_slots: ['', ''],
    externals_str: '',
    backpack: ['', '', '', '', '', ''],
    secrets_str: '',
    darkvision: false, vision_range: 6, listen_radius: 6,
    passive_perception: 10, stealth: 0,
  }
}

function startEdit(s: CharacterSheet) {
  editing.value = {
    id: s.id,
    name: s.name || '',
    avatar_url: s.avatar_url || '',
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
    darkvision: s.darkvision ?? false,
    vision_range: s.vision_range ?? 6,
    listen_radius: s.listen_radius ?? 6,
    passive_perception: s.passive_perception ?? 10,
    stealth: s.stealth ?? 0,
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
  // Phase 4: 创造点硬校验
  if (usedCP.value > 30) {
    error.value = `创造点超限！已用 ${usedCP.value}，上限 30，请减少 ${usedCP.value - 30} 点`
    return
  }

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
    avatar_url: e.avatar_url || null,
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
    darkvision: e.darkvision,
    vision_range: e.vision_range,
    listen_radius: e.listen_radius,
    passive_perception: e.passive_perception,
    stealth: e.stealth,
  }
  try {
    if (e.id) {
      await updateCharacter(e.id, body)
    } else {
      await createCharacter(body)
    }
    saved.value = true
    await load()
    window.dispatchEvent(new CustomEvent('sheets-changed'))  // 通知资源库「我的角色卡」刷新
  } catch (err: any) {
    error.value = err.message || '保存失败'
  }
}

async function onDelete(s: CharacterSheet) {
  if (!confirm(`确定删除角色卡「${s.name}」？`)) return
  try {
    await deleteCharacter(s.id)
    await load()
    window.dispatchEvent(new CustomEvent('sheets-changed'))  // 通知资源库「我的角色卡」刷新
    if (editing.value?.id === s.id) editing.value = null
  } catch (err: any) {
    error.value = err.message
  }
}

function onDragStart(e: DragEvent, s: CharacterSheet) {
  dragSheetId.value = s.id
  e.dataTransfer?.setData('application/json', JSON.stringify({
    kind: 'character_sheet', sheet: s,
  }))
  e.dataTransfer!.effectAllowed = 'copy'
  // 设置拖拽时的视觉反馈图片
  const el = e.target as HTMLElement
  if (el) {
    e.dataTransfer?.setDragImage(el, 10, 10)
  }
}

async function onAvatarUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !editing.value) return
  uploading.value = true
  try {
    editing.value.avatar_url = await uploadAvatar(file)
  } catch (err) {
    error.value = '头像上传失败: ' + (err as Error).message
  } finally {
    uploading.value = false
    input.value = ''
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
.drag-handle { color: #bbb; margin-right: 6px; font-size: 12px; cursor: grab; }
.sheet-list li.dragging { opacity: 0.5; background: #e0f0ff; }
.form { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.form h4 { margin: 0 0 4px; font-size: 15px; }
.block { border: 1px solid #eee; border-radius: 4px; padding: 10px; background: #fafafa; }
.block h5 { margin: 0 0 8px; font-size: 13px; color: #0f3460;
  border-bottom: 1px dashed #ccc; padding-bottom: 4px; }
.cp-hint { font-size: 11px; color: #888; font-weight: normal; }
.cp-over { color: #c00 !important; font-weight: bold; }
.avatar-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.avatar-preview { width: 40px; height: 40px; border-radius: 50%; background: #0f3460;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: 600; flex-shrink: 0; overflow: hidden; }
.avatar-preview img { width: 100%; height: 100%; object-fit: cover; }
.avatar-upload-btn { font-size: 11px; color: #0f3460; border: 1px dashed #0f3460;
  border-radius: 4px; padding: 4px 8px; cursor: pointer; }
.avatar-upload-btn:hover { background: #eef3fb; }
.avatar-clear { font-size: 11px; padding: 4px 8px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.grid-nums { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.grid-nums label { display: flex; flex-direction: column; font-size: 11px; color: #666; }
.check-row { display: flex; align-items: center; gap: 6px; font-size: 12px;
  color: #0f3460; margin-bottom: 8px; cursor: pointer; }
.check-row input { width: auto; margin: 0; }
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
