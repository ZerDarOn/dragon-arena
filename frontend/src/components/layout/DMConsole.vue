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
      <div class="brush-group">
        <label>地貌</label>
        <div class="brush-row">
          <button v-for="t in terrainTypes" :key="t.v" @click="selected = t.v"
                  :class="{ active: selected === t.v }">{{ t.l }}</button>
        </div>
      </div>
      <div class="brush-group">
        <label>环境</label>
        <div class="brush-row">
          <button v-for="t in envTypes" :key="t.v" @click="selected = t.v"
                  :class="{ active: selected === t.v }">{{ t.l }}</button>
        </div>
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
      <label>安全区半径 <code>{{ poisonRadius }}</code></label>
      <input type="range" v-model.number="poisonRadius" min="0" max="50" @change="emitPoison" />
      <button class="btn-primary" @click="emitPoison">应用毒圈设置</button>
      <p class="hint">圈内=安全区，圈外=毒圈（每回合受伤）。调小半径=安全区收缩，直到 0 消失。</p>
    </div>

    <!-- 迷雾控制 -->
    <div v-if="activeTab === 'fog'" class="panel">
      <label class="check-row">
        <input type="checkbox" v-model="fogEnabled" @change="emitFog" />
        <span>启用战争迷雾</span>
      </label>
      <p class="hint">关闭后所有玩家可见全图</p>
      <hr />
      <label class="check-row">
        <input type="checkbox" v-model="allowPlacement" @change="emitPlacement" />
        <span>允许玩家自助落子</span>
      </label>
      <p class="hint">默认关闭——由你统一安排落子。开启后玩家可自行选择角色卡落子</p>
    </div>

    <!-- 模式与落子 -->
    <div v-if="activeTab === 'mode'" class="panel">
      <label class="check-row">
        <input type="checkbox" v-model="freeMode" @change="emitFreeMode" />
        <span>自由模式（测试用）</span>
      </label>
      <p class="warn">⚠ 忽略 AP/回合/落子等所有规则限制，所有人可随意操作</p>
      <hr />
      <label class="check-row">
        <input type="checkbox" v-model="allowPlacement" @change="emitPlacement" />
        <span>允许玩家自助落子</span>
      </label>
      <hr />
      <div class="placement-group">
        <label>随机落子（未落子的玩家）</label>
        <div class="btn-row">
          <button class="btn" @click="emitRandom('all')">全图随机</button>
          <button class="btn" @click="emitRandom('edge')">边缘分布</button>
        </div>
        <div class="coord">
          <input v-model.number="ax1" type="number" placeholder="x1" />
          <input v-model.number="ay1" type="number" placeholder="y1" />
          <span>→</span>
          <input v-model.number="ax2" type="number" placeholder="x2" />
          <input v-model.number="ay2" type="number" placeholder="y2" />
          <button class="btn" @click="emitRandom('area')">区域内</button>
        </div>
      </div>
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

    <!-- 地图尺寸 + 底图对齐 -->
    <div v-if="activeTab === 'map'" class="panel">
      <label>宽度 <code>{{ w }}</code></label>
      <input type="range" v-model.number="w" min="10" max="80" @change="emitResize" />
      <label>高度 <code>{{ h }}</code></label>
      <input type="range" v-model.number="h" min="10" max="80" @change="emitResize" />
      <p class="warn">⚠ 调整尺寸会清空整张地图已绘制的地形（不只是超界区域），且不可撤销</p>
      <hr />
      <h4>底图对齐</h4>
      <div class="bg-align-grid">
        <label>X 偏移 <code>{{ bgOX.toFixed(1) }}</code></label>
        <input type="range" v-model.number="bgOX" min="-20" max="20" step="0.5" @change="emitBgTransform" />
        <label>Y 偏移 <code>{{ bgOY.toFixed(1) }}</code></label>
        <input type="range" v-model.number="bgOY" min="-20" max="20" step="0.5" @change="emitBgTransform" />
        <label>X 缩放 <code>{{ bgSX.toFixed(2) }}</code></label>
        <input type="range" v-model.number="bgSX" min="0.2" max="3" step="0.05" @change="emitBgTransform" />
        <label>Y 缩放 <code>{{ bgSY.toFixed(2) }}</code></label>
        <input type="range" v-model.number="bgSY" min="0.2" max="3" step="0.05" @change="emitBgTransform" />
      </div>
      <button class="btn" @click="resetBgTransform">重置变换</button>
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
  (e: 'set-player-placement', enabled: boolean): void
  (e: 'set-free-mode', enabled: boolean): void
  (e: 'random-placement', mode: string, area?: { x1: number; y1: number; x2: number; y2: number }): void
  (e: 'bg-transform', t: { offset_x: number; offset_y: number; scale_x: number; scale_y: number }): void
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
    { key: 'mode', label: '模式' },
    { key: 'turn', label: '回合' },
    { key: 'map', label: '地图' },
]

// Terrain brush
const selected = ref('')
const lightRadius = ref(3)  // 光源笔刷半径
const terrainTypes = [
  { v: '', l: '关闭' },
  { v: 'flat', l: '平地' }, { v: 'wall', l: '墙' },
  { v: 'grass', l: '草丛' }, { v: 'water', l: '水' }, { v: 'high', l: '高地' },
]
const envTypes = [
  { v: 'dark', l: '黑暗' }, { v: 'light', l: '光源' }, { v: 'clear_meta', l: '清暗/光' },
]
const typeLabel = computed(() => {
  const all = [...terrainTypes, ...envTypes]
  return all.find((t) => t.v === selected.value)?.l ?? ''
})

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

// Player placement permission
const allowPlacement = ref(false)
function emitPlacement() {
  emit('set-player-placement', allowPlacement.value)
}

// Free mode (测试用：忽略所有规则限制)
const freeMode = ref(false)
function emitFreeMode() {
  emit('set-free-mode', freeMode.value)
}

// 随机落子
const ax1 = ref(0); const ay1 = ref(0)
const ax2 = ref(10); const ay2 = ref(10)
function emitRandom(mode: string) {
  if (mode === 'area') {
    emit('random-placement', mode, { x1: ax1.value, y1: ay1.value, x2: ax2.value, y2: ay2.value })
  } else {
    emit('random-placement', mode)
  }
}

// 底图对齐变换
const bgOX = ref(0); const bgOY = ref(0)
const bgSX = ref(1); const bgSY = ref(1)
function emitBgTransform() {
  emit('bg-transform', {
    offset_x: bgOX.value, offset_y: bgOY.value,
    scale_x: bgSX.value, scale_y: bgSY.value,
  })
}
function resetBgTransform() {
  bgOX.value = 0; bgOY.value = 0; bgSX.value = 1; bgSY.value = 1
  emitBgTransform()
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
.brush-row { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 4px; }
.brush-row button { padding: 4px 8px; border: 1px solid #ccc; background: #fff;
  border-radius: 3px; cursor: pointer; font-size: 11px; }
.brush-row button.active { background: #fa0; color: #fff; border-color: #fa0; }
.brush-group { margin-bottom: 8px; }
.brush-group > label { display: block; font-size: 10px; color: #888; margin-bottom: 4px;
  text-transform: uppercase; letter-spacing: 0.5px; }
.paint-modes { display: flex; gap: 4px; margin-bottom: 8px; }
.paint-modes button { padding: 3px 8px; border: 1px solid #ccc; background: #fff; border-radius: 3px; cursor: pointer; font-size: 11px; }
.paint-modes button.active { background: #0f3460; color: #fff; border-color: #0f3460; }
.fill-tool { border-top: 1px dashed #ddd; padding-top: 8px; }
.fill-tool label { display: block; font-size: 11px; color: #666; margin-bottom: 4px; }
.coord { display: flex; gap: 4px; align-items: center; flex-wrap: wrap; }
.coord input { width: 40px; padding: 3px; font-size: 11px; border: 1px solid #ccc; border-radius: 2px; }
.coord select { padding: 3px; font-size: 11px; }
.coord button { padding: 4px 8px; background: #0f3460; color: #fff; border: none; border-radius: 2px; cursor: pointer; }
.bg-align-grid { display: grid; gap: 6px; margin: 6px 0; }
.bg-align-grid label { font-size: 11px; color: #555; display: flex; justify-content: space-between; }
.bg-align-grid code { color: #0f3460; font-weight: bold; }
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
