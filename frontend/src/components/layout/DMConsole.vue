<template>
  <div class="dm-console">
    <div class="tabs">
      <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
              :class="{ active: activeTab === tab.key }">{{ tab.label }}</button>
    </div>

    <!-- 地形笔刷 -->
    <div v-if="activeTab === 'terrain'" class="panel">
      <div class="paint-modes">
        <button v-for="m in paintModes" :key="m.v" @click="paintMode = m.v"
                :class="{ active: paintMode === m.v }">{{ m.l }}</button>
      </div>
      <div class="brush-row">
        <button v-for="t in types" :key="t.v" @click="selected = t.v"
                :class="{ active: selected === t.v }">{{ t.l }}</button>
      </div>
      <div class="fill-tool">
        <label>批量填充</label>
        <div class="coord">
          <input v-model.number="fx1" type="number" placeholder="x1" />
          <input v-model.number="fy1" type="number" placeholder="y1" />
          <span>→</span>
          <input v-model.number="fx2" type="number" placeholder="x2" />
          <input v-model.number="fy2" type="number" placeholder="y2" />
          <select v-model="fillType">
            <option value="wall">墙</option>
            <option value="grass">草</option>
            <option value="water">水</option>
            <option value="high">高地</option>
            <option value="flat">平地</option>
          </select>
          <button @click="doFill">填充</button>
        </div>
      </div>
      <p class="hint" v-if="selected">
        <span v-if="paintMode === 'single'">点击/拖拽涂抹「{{ typeLabel }}」</span>
        <span v-else-if="paintMode === 'line'">拖拽画线应用「{{ typeLabel }}」</span>
        <span v-else-if="paintMode === 'rect'">拖拽矩形填充「{{ typeLabel }}」</span>
        <span v-if="selected === 'light'">（半径{{ lightRadius }}）</span>
      </p>
      <div v-if="selected === 'light'" class="light-config">
        <label>光源半径 <code>{{ lightRadius }}</code></label>
        <input type="range" min="1" max="10" v-model.number="lightRadius" />
      </div>
    </div>

    <!-- 毒圈控制 -->
    <div v-if="activeTab === 'poison'" class="panel">
      <label class="check-row">
        <input type="checkbox" v-model="poisonEnabled" @change="emitPoison" />
        <span>启用毒圈</span>
      </label>
      <div class="row">
        <label>中心X <input type="number" v-model.number="poisonCX" @change="emitPoison" /></label>
        <label>中心Y <input type="number" v-model.number="poisonCY" @change="emitPoison" /></label>
      </div>
      <label>半径 <code>{{ poisonRadius }}</code></label>
      <input type="range" v-model.number="poisonRadius" min="1" max="50" @change="emitPoison" />
      <button class="btn-primary" @click="emitPoison">应用毒圈设置</button>
    </div>

    <!-- 迷雾控制 -->
    <div v-if="activeTab === 'fog'" class="panel">
      <label class="check-row">
        <input type="checkbox" v-model="fogEnabled" @change="emitFog" />
        <span>启用战争迷雾</span>
      </label>
      <p class="hint">关闭后所有玩家可见全图</p>
    </div>

    <!-- 回合控制 -->
    <div v-if="activeTab === 'turn'" class="panel">
      <label>回合顺序（用逗号分隔token ID）</label>
      <textarea v-model="turnOrderText" rows="3" class="order-text" />
      <div class="btn-row">
        <button class="btn-primary" @click="emitSetOrder">设置顺序</button>
        <button class="btn" @click="emitShuffle">随机打乱</button>
      </div>
      <label>强制指定当前回合</label>
      <input v-model="forceActorId" placeholder="token ID" />
      <button class="btn-primary" @click="emitForceActor">强制指定</button>
      <hr />
      <button class="btn-danger" @click="emitClearLog">清除战斗日志</button>
    </div>

    <!-- 地图尺寸 -->
    <div v-if="activeTab === 'map'" class="panel">
      <label>宽度 <code>{{ w }}</code></label>
      <input type="range" v-model.number="w" min="10" max="80" @change="emitResize" />
      <label>高度 <code>{{ h }}</code></label>
      <input type="range" v-model.number="h" min="10" max="80" @change="emitResize" />
      <p class="warn">⚠ 调整尺寸会清空整张地图已绘制的地形（不只是超界区域），且不可撤销</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const emit = defineEmits<{
  (e: 'resize', w: number, h: number): void
  (e: 'fill-area', area: { x1: number; y1: number; x2: number; y2: number; type: string }): void
  (e: 'set-poison-circle', cfg: { center_x: number; center_y: number; radius: number; enabled: boolean }): void
  (e: 'set-fog-of-war', enabled: boolean): void
  (e: 'set-turn-order', order: string[]): void
  (e: 'shuffle-turn-order'): void
  (e: 'force-set-actor', tokenId: string): void
  (e: 'clear-combat-log'): void
}>()

const activeTab = ref('terrain')
const tabs = [
  { key: 'terrain', label: '地形' },
    { key: 'poison', label: '毒圈' },
    { key: 'fog', label: '迷雾' },
    { key: 'turn', label: '回合' },
    { key: 'map', label: '地图' },
]

// Terrain brush
const selected = ref('')
const lightRadius = ref(3)  // 光源笔刷半径
const types = [
  { v: '', l: '关闭' }, { v: 'flat', l: '平地' }, { v: 'wall', l: '墙' },
  { v: 'grass', l: '草丛' }, { v: 'water', l: '水' }, { v: 'high', l: '高地' },
  { v: 'dark', l: '黑暗' }, { v: 'light', l: '光源' }, { v: 'clear_meta', l: '清黑暗/光' },
]
const typeLabel = computed(() => types.find((t) => t.v === selected.value)?.l ?? '')

// 笔刷模式
const paintMode = ref<'single' | 'line' | 'rect'>('single')
const paintModes = [
  { v: 'single' as const, l: '涂抹' },
  { v: 'line' as const, l: '画线' },
  { v: 'rect' as const, l: '矩形' },
]

// Fill
const fx1 = ref(0); const fy1 = ref(0); const fx2 = ref(5); const fy2 = ref(5)
const fillType = ref('wall')

function doFill() {
  emit('fill-area', {
    x1: Math.min(fx1.value, fx2.value), y1: Math.min(fy1.value, fy2.value),
    x2: Math.max(fx1.value, fx2.value), y2: Math.max(fy1.value, fy2.value),
    type: fillType.value,
  })
}

// Map size
const w = ref(30); const h = ref(30)
function emitResize() {
  if (!confirm('调整地图尺寸会清空整张地图已绘制的全部地形（墙/草/水/光源/黑暗），且不可撤销，确定继续吗？')) {
    return
  }
  emit('resize', w.value, h.value)
}

// Poison circle
const poisonEnabled = ref(true)
const poisonCX = ref(15)
const poisonCY = ref(15)
const poisonRadius = ref(15)
function emitPoison() {
  emit('set-poison-circle', {
    center_x: poisonCX.value,
    center_y: poisonCY.value,
    radius: poisonRadius.value,
    enabled: poisonEnabled.value,
  })
}

// Fog of war
const fogEnabled = ref(true)
function emitFog() {
  emit('set-fog-of-war', fogEnabled.value)
}

// Turn order
const turnOrderText = ref('')
function emitSetOrder() {
  const order = turnOrderText.value.split(',').map(s => s.trim()).filter(Boolean)
  emit('set-turn-order', order)
}
function emitShuffle() {
  emit('shuffle-turn-order')
}
const forceActorId = ref('')
function emitForceActor() {
  if (forceActorId.value) emit('force-set-actor', forceActorId.value)
}
function emitClearLog() {
  emit('clear-combat-log')
}

defineExpose({
  selected,
  lightRadius,
  paintMode,
})
</script>

<style scoped>
.dm-console { background: #f5f5f5; border-bottom: 1px solid #ccc; font-size: 12px; }
.tabs { display: flex; border-bottom: 1px solid #ddd; }
.tabs button { flex: 1; padding: 6px; border: none; background: transparent; cursor: pointer;
  font-size: 12px; border-bottom: 2px solid transparent; }
.tabs button.active { background: #fff; border-bottom-color: #fa0; font-weight: bold; }
.panel { padding: 8px; }
.brush-row { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.brush-row button { padding: 4px 8px; border: 1px solid #ccc; background: #fff;
  border-radius: 3px; cursor: pointer; font-size: 11px; }
.brush-row button.active { background: #fa0; color: #fff; border-color: #fa0; }
.paint-modes { display: flex; gap: 4px; margin-bottom: 8px; }
.paint-modes button { padding: 3px 8px; border: 1px solid #ccc; background: #fff; border-radius: 3px; cursor: pointer; font-size: 11px; }
.paint-modes button.active { background: #0f3460; color: #fff; border-color: #0f3460; }
.fill-tool { border-top: 1px dashed #ddd; padding-top: 8px; }
.fill-tool label { display: block; font-size: 11px; color: #666; margin-bottom: 4px; }
.coord { display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }
.coord input { width: 40px; padding: 3px; font-size: 11px; border: 1px solid #ccc; border-radius: 2px; }
.coord select { padding: 3px; font-size: 11px; }
.coord button { padding: 4px 8px; background: #0f3460; color: #fff; border: none; border-radius: 2px; cursor: pointer; }
.hint { margin: 6px 0 0; color: #888; font-size: 11px; }
.tmpl-pick { margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px dashed #ddd; }
.tmpl-pick label { font-size: 10px; color: #666; margin-right: 4px; }
.tmpl-pick select { width: 100%; padding: 3px; font-size: 11px; }
.light-config { margin-top: 6px; padding-top: 6px; border-top: 1px dashed #ddd; }
.light-config label { display: block; font-size: 11px; color: #666; margin-bottom: 4px; }
.warn { margin: 6px 0 0; color: #c33; font-size: 11px; }
select, input[type=text], input:not([type]):not([type=number]):not([type=range]) {
  padding: 4px; font-size: 12px; border: 1px solid #ccc; border-radius: 3px; }
.row { display: flex; gap: 8px; margin-top: 6px; }
.row label { display: flex; flex-direction: column; font-size: 11px; color: #666; flex: 1; }
.row input { margin-top: 2px; }
input[type=range] { width: 100%; }
code { background: #eee; padding: 1px 4px; border-radius: 2px; font-family: monospace; }
</style>
