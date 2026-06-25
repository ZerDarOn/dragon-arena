<template>
  <div class="canvas-scroll" ref="scrollRef"
       @wheel.prevent="onWheel"
       @mousedown="onDown"
       @mousemove="onMouseMove"
       @mouseup="onMouseUp"
       @mouseleave="onMouseUp"
       @dblclick="onDblClick"
       @drop="onDrop"
       @dragover.prevent=""
       @contextmenu.prevent="onContextMenu">
    <canvas ref="canvasRef"
            :style="canvasStyle" />

    <!-- FVTT-style radial action menu (右键触发) -->
    <div v-if="showRadial" class="radial-menu" :style="radialMenuStyle" @mousedown.stop @click.stop>
      <button class="radial-btn move" @mousedown.stop @click.stop="doRadial('move')" title="移动">移动</button>
      <button class="radial-btn attack" @mousedown.stop @click.stop="doRadial('attack')" title="攻击">攻击</button>
      <button class="radial-btn info" @mousedown.stop @click.stop="doRadial('info')" title="详情">详情</button>
      <button class="radial-btn dismiss" @mousedown.stop @click.stop="doRadial('dismiss')" title="取消">✕</button>
    </div>

    <!-- Scale drag handle (右下角小三角) -->
    <div v-if="selectedOverlay" class="scale-handle" :style="scaleHandleStyle"
         @mousedown.stop="onScaleDragStart"
         @mousemove.stop="onScaleDrag"
         @mouseup.stop="onScaleDragEnd"
         @mouseleave.stop="onScaleDragEnd"
         title="拖拽缩放">⤡</div>

    <div class="vp-hud">
      <button @click="setTool('select')" :class="{ active: tool === 'select' }">选择</button>
      <button @click="setTool('measure')" :class="{ active: tool === 'measure' }">测距</button>
      <button @click="setTool('cone')" :class="{ active: tool === 'cone' }">扇形</button>
      <button @click="setTool('line')" :class="{ active: tool === 'line' }">直线</button>
      <button @click="setTool('sphere')" :class="{ active: tool === 'sphere' }">球型</button>
      <button @click="setTool('draw')" :class="{ active: tool === 'draw' }">手绘</button>
      <div v-if="tool === 'draw'" class="color-pick">
        <button v-for="(c, i) in DRAW_COLORS" :key="c" class="color-chip"
                :style="{ background: c }" :class="{ active: drawColorIdx === i }"
                @click="drawColorIdx = i" />
      </div>
      <span class="sep">|</span>
      <button @click="zoomBy(-0.1, vpW()/2, vpH()/2)">−</button>
      <span>{{ Math.round(zoom * 100) }}%</span>
      <button @click="zoomBy(0.1, vpW()/2, vpH()/2)">+</button>
      <button @click="resetView">复位</button>
      <span class="sep">|</span>
      <button @click="clearMarkers" title="清除所有标记/手绘">🧹清除</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, onUnmounted } from 'vue'
import type { Room } from '../../api/types'

const props = defineProps<{
  room: Room
  selfTokenId?: string
  visibleCells?: Set<string>
  exploredCells?: Set<string>
  fogOfWarEnabled?: boolean
  detectedTokens?: Record<string, string>  // {tokenId: 方位名}
  terrainBrush?: string
  lightRadius?: number
  isAdmin?: boolean
  bgImage?: string      // 底图 dataURL
  bgOpacity?: number    // 0-1
  combatMode?: 'attack' | 'sprint' | null  // 战斗模式
}>()
const emit = defineEmits<{
  (e: 'path-committed', path: [number, number][]): void
  (e: 'cell-click', cell: { x: number; y: number; action?: string }): void
  (e: 'token-selected', token: any): void
  (e: 'token-rotate', tokenId: string, facing: number): void
  (e: 'token-size', tokenId: string, size: number): void
  (e: 'token-dblclick', token: any): void
  (e: 'spawn-actor', payload: { actor_id: string; x: number; y: number }): void
  (e: 'spawn-sheet', payload: { sheet: any; x: number; y: number }): void
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const scrollRef = ref<HTMLDivElement | null>(null)
const CELL = 32

// --- 视口 ---
const pan = ref({ x: 0, y: 0 })
const zoom = ref(1)
type ToolName = 'select' | 'measure' | 'cone' | 'line' | 'sphere' | 'draw'
const tool = ref<ToolName>('select')

function vpW() { return scrollRef.value?.clientWidth ?? 800 }
function vpH() { return scrollRef.value?.clientHeight ?? 600 }

const canvasStyle = computed(() => ({
  transform: `translate(${pan.value.x}px, ${pan.value.y}px) scale(${zoom.value})`,
  transformOrigin: '0 0',
  position: 'absolute' as const,
  left: '0', top: '0',
  width: `${props.room.config.map_width * CELL}px`,
  height: `${props.room.config.map_height * CELL}px`,
}))

// --- 状态 ---
const dragging = ref(false)
const dragPath = ref<[number, number][]>([])
const panning = ref(false)
const panStart = ref({ mx: 0, my: 0, px: 0, py: 0 })
const painting = ref(false)  // 笔刷连续涂抹
const paintedCells = ref<Set<string>>(new Set())  // 本次涂抹已画的格子
const measuring = ref(false)
const measureStart = ref<[number, number] | null>(null)
const measureEnd = ref<[number, number] | null>(null)
const selectedTokenId = ref<string | null>(null)
const hoveredCell = ref<[number, number] | null>(null)
const dragStartForCancel = ref<[number, number] | null>(null)  // 空白处点击起点，区分单击取消 vs 拖动

// 地形笔刷模式：single=单格涂抹, line=画线, rect=矩形填充
const terrainPaintMode = ref<'single' | 'line' | 'rect'>('single')
const terrainPaintStart = ref<[number, number] | null>(null)
const terrainPaintPreview = ref<[number, number][]>([])
const terrainPaintQueue = ref<{x: number, y: number, type: string, meta?: any}[]>([])

// AOE 模板标记（松开后保留显示）
interface AoeMarker {
  kind: 'cone' | 'line' | 'sphere' | 'measure'
  start: [number, number]
  end: [number, number]
}
const aoeMarkers = ref<AoeMarker[]>([])
const currentAoe = ref<AoeMarker | null>(null)

// 手绘注释（世界像素坐标点序列）
interface DrawStroke {
  points: [number, number][]
  color: string
}
const drawStrokes = ref<DrawStroke[]>([])
const currentStroke = ref<DrawStroke | null>(null)
const DRAW_COLORS = ['#ff4040', '#40c0ff', '#40ff40', '#ffff40', '#ff40ff', '#ffffff']
const drawColorIdx = ref(0)

// 头像缓存
const avatarCache = ref<Record<string, HTMLImageElement>>({})

// 预加载头像
watch(() => props.room.tokens, (tokens) => {
  for (const t of Object.values(tokens)) {
    if (t.avatar_url && !avatarCache.value[t.avatar_url]) {
      const img = new Image()
      img.src = t.avatar_url
      img.onload = () => { draw() }
      avatarCache.value[t.avatar_url] = img
    }
  }
}, { immediate: true, deep: true })

const selectedToken = computed(() =>
  selectedTokenId.value ? props.room.tokens[selectedTokenId.value] : null
)

// 径向菜单
const showRadial = ref(false)

// 选中棋子的控件位置（屏幕像素）
const selectedOverlay = computed(() => {
  const t = selectedToken.value
  if (!t?.position) return null
  const tkSize = t.size || 1
  const sx = t.position.x * CELL * zoom.value + pan.value.x
  const sy = t.position.y * CELL * zoom.value + pan.value.y
  return { left: `${sx}px`, top: `${sy}px`, w: CELL * tkSize * zoom.value }
})

const radialMenuStyle = computed(() => {
  const pos = selectedOverlay.value
  if (!pos) return {}
  return { left: `calc(${pos.left} + ${pos.w / 2}px)`, top: `calc(${pos.top} + ${pos.w / 2}px)` }
})

const scaleHandleStyle = computed(() => {
  const pos = selectedOverlay.value
  if (!pos) return { display: 'none' }
  return { left: `calc(${pos.left} + ${pos.w + 2}px)`, top: `calc(${pos.top} + ${pos.w + 2}px)` }
})

// 大小拖拽（占格数 1-4）
const sizeDragging = ref(false)
const sizeDragStartY = ref(0)
const sizeDragStartVal = ref(1)
function onScaleDragStart(e: MouseEvent) {
  sizeDragging.value = true
  sizeDragStartY.value = e.clientY
  sizeDragStartVal.value = selectedToken.value?.size || 1
}
function onScaleDrag(_e: MouseEvent) {
  if (!sizeDragging.value || !selectedToken.value) return
}
function onScaleDragEnd(e: MouseEvent) {
  if (!sizeDragging.value || !selectedToken.value) return
  sizeDragging.value = false
  const delta = (sizeDragStartY.value - e.clientY) * 0.03
  const newSize = Math.max(1, Math.min(4, Math.round(sizeDragStartVal.value + delta)))
  emit('token-size', selectedToken.value.id, newSize)
}

function doRadial(action: string) {
  showRadial.value = false
  if (!selectedToken.value) return
  if (action === 'info') {
    emit('token-dblclick', selectedToken.value)
  } else if (action === 'move' || action === 'attack') {
    // move：棋子已选中，click-to-move 已就绪，提示点目标格即可；attack：进入攻击模式
    emit('cell-click', { x: selectedToken.value.position!.x, y: selectedToken.value.position!.y, action })
  }
}

function setTool(t: ToolName) {
  tool.value = t
  selectedTokenId.value = null
  currentAoe.value = null
  currentStroke.value = null
}

function clearMarkers() {
  aoeMarkers.value = []
  drawStrokes.value = []
  currentAoe.value = null
  currentStroke.value = null
  draw()
}

// 底图 Image 缓存（dataURL -> HTMLImageElement）
const bgImgCache = new Map<string, HTMLImageElement>()
const bgImgLoading = new Set<string>()
function getBgImg(dataUrl: string): HTMLImageElement | null {
  if (bgImgCache.has(dataUrl)) return bgImgCache.get(dataUrl)!
  if (bgImgLoading.has(dataUrl)) return null
  bgImgLoading.add(dataUrl)
  const img = new Image()
  img.onload = () => { bgImgLoading.delete(dataUrl); draw() }
  img.onerror = () => { bgImgLoading.delete(dataUrl) }
  img.src = dataUrl
  bgImgCache.set(dataUrl, img)
  return null  // 首次返回 null，加载完成后 onload 触发重绘
}

function key(x: number, y: number) { return `${x},${y}` }

// Bresenham 画线算法：返回从 (x0,y0) 到 (x1,y1) 的所有格子
function bresenhamLine(x0: number, y0: number, x1: number, y1: number): [number, number][] {
  const points: [number, number][] = []
  const dx = Math.abs(x1 - x0), dy = Math.abs(y1 - y0)
  const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1
  let err = dx - dy
  let x = x0, y = y0
  while (true) {
    points.push([x, y])
    if (x === x1 && y === y1) break
    const e2 = 2 * err
    if (e2 > -dy) { err -= dy; x += sx }
    if (e2 < dx) { err += dx; y += sy }
  }
  return points
}

// 矩形区域：返回从 (x0,y0) 到 (x1,y1) 矩形内所有格子
function rectCells(x0: number, y0: number, x1: number, y1: number): [number, number][] {
  const points: [number, number][] = []
  const minX = Math.min(x0, x1), maxX = Math.max(x0, x1)
  const minY = Math.min(y0, y1), maxY = Math.max(y0, y1)
  for (let y = minY; y <= maxY; y++) {
    for (let x = minX; x <= maxX; x++) {
      points.push([x, y])
    }
  }
  return points
}

// 颜色混合：a 与 b 按 t 比例混合（t=0 全 a, t=1 全 b）
function mixColor(a: string, b: string, t: number): string {
  const pa = hexToRgb(a), pb = hexToRgb(b)
  if (!pa || !pb) return a
  const r = Math.round(pa[0] + (pb[0] - pa[0]) * t)
  const g = Math.round(pa[1] + (pb[1] - pa[1]) * t)
  const bl = Math.round(pa[2] + (pb[2] - pa[2]) * t)
  return `rgb(${r},${g},${bl})`
}
function hexToRgb(hex: string): [number, number, number] | null {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex)
  if (!m) return null
  let h = m[1]
  if (h.length === 3) h = h.split('').map(c => c + c).join('')
  return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)]
}

const TERRAIN_COLORS: Record<string, string> = {
  flat: '#f0f0f0', wall: '#444', grass: '#9c9', water: '#7cf',
  high: '#da6', smoke: '#ccc',
}

/**
 * draw() — 四层渲染管道
 *   L1 底图 → L2 地形 → L3 暗/光 → L4 战争迷雾 → Token → UI
 */
function draw() {
  const cv = canvasRef.value; if (!cv) return
  const ctx = cv.getContext('2d')!
  const cfg = props.room.config
  const dpr = window.devicePixelRatio || 1
  const cssW = cfg.map_width * CELL
  const cssH = cfg.map_height * CELL
  cv.width = cssW * dpr; cv.height = cssH * dpr
  cv.style.width = `${cssW}px`; cv.style.height = `${cssH}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cssW, cssH)

  drawLayer1_Background(ctx, cv)
  drawLayer2_Terrain(ctx)
  drawLayer3_DarknessAndLight(ctx)
  drawLayer4_FogOfWar(ctx)
  drawTerrainPaintPreview(ctx)
  drawTerrainHover(ctx)
  drawAoeMarkers(ctx)
  drawStrokes_(ctx)
  drawTokens(ctx)
  drawPoisonCircle(ctx)
  drawDetectedMarkers(ctx)
  drawDragPath(ctx)
}

/* ================================================================
   Layer 1 — 底图
   ================================================================ */
function drawLayer1_Background(ctx: CanvasRenderingContext2D, cv: HTMLCanvasElement) {
  if (!props.bgImage) return
  const img = getBgImg(props.bgImage)
  if (!img) return
  ctx.globalAlpha = props.bgOpacity ?? 0.5
  ctx.drawImage(img, 0, 0, cv.width, cv.height)
  ctx.globalAlpha = 1
}

/* ================================================================
   Layer 2 — 地形瓦片
   ================================================================ */
function drawLayer2_Terrain(ctx: CanvasRenderingContext2D) {
  const cfg = props.room.config
  const map = props.room.game_map
  for (let y = 0; y < cfg.map_height; y++) {
    for (let x = 0; x < cfg.map_width; x++) {
      const vis = !props.visibleCells || props.visibleCells.has(key(x, y))
      if (!vis) { ctx.fillStyle = '#222'; ctx.fillRect(x * CELL, y * CELL, CELL, CELL); continue }
      let bg = '#f0f0f0'
      if (map?.terrain[y]?.[x]) {
        const cell = map.terrain[y][x]
        bg = TERRAIN_COLORS[cell.type] || '#f0f0f0'
        if (cell.is_smoke) bg = '#bbb'
        // 光源暖黄（不与暗 mix，暗由 Layer 3 单独处理）
        if (cell.light_radius > 0) bg = mixColor(bg, '#ff8', 0.35)
        if (cell.height) {
          ctx.fillStyle = bg; ctx.fillRect(x * CELL, y * CELL, CELL, CELL)
          ctx.fillStyle = '#603'; ctx.font = '10px monospace'
          ctx.fillText(String(cell.height), x * CELL + 2, y * CELL + 10)
          continue
        }
      }
      ctx.fillStyle = bg; ctx.fillRect(x * CELL, y * CELL, CELL, CELL)
      ctx.strokeStyle = '#999'; ctx.lineWidth = 1
      ctx.strokeRect(x * CELL, y * CELL, CELL, CELL)
    }
  }
}

/* ================================================================
   Layer 3 — 环境暗 + 光源（全局合成模式挖洞）
   ================================================================ */
function drawLayer3_DarknessAndLight(ctx: CanvasRenderingContext2D) {
  const cfg = props.room.config
  const map = props.room.game_map
  if (!map) return

  // Pass 1: 画暗层
  for (let y = 0; y < cfg.map_height; y++) {
    for (let x = 0; x < cfg.map_width; x++) {
      const cell = map.terrain[y]?.[x]
      if (!cell?.is_dark) continue
      if (props.isAdmin) continue
      const strength = cell.darkness_strength ?? 0.7
      ctx.fillStyle = `rgba(0, 0, 0, ${strength * 0.75})`
      ctx.fillRect(x * CELL, y * CELL, CELL, CELL)
    }
  }

  // Pass 2: 光源挖洞（在暗层上擦出亮区）
  ctx.globalCompositeOperation = 'destination-out'
  for (let y = 0; y < cfg.map_height; y++) {
    for (let x = 0; x < cfg.map_width; x++) {
      const cell = map.terrain[y]?.[x]
      if (!cell || cell.light_radius <= 0) continue
      const radius = cell.light_radius * CELL
      const cx = x * CELL + CELL / 2
      const cy = y * CELL + CELL / 2
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius)
      grad.addColorStop(0, 'rgba(0,0,0,1)')
      grad.addColorStop(0.6, 'rgba(0,0,0,0.5)')
      grad.addColorStop(1, 'rgba(0,0,0,0)')
      ctx.fillStyle = grad
      ctx.fillRect(cx - radius, cy - radius, radius * 2, radius * 2)
    }
  }
  ctx.globalCompositeOperation = 'source-over'
}

/* ================================================================
   Layer 4 — 战争迷雾（黑幕 + 记忆灰层）
   ================================================================ */
function drawLayer4_FogOfWar(ctx: CanvasRenderingContext2D) {
  if (props.isAdmin) return
  if (!props.fogOfWarEnabled) return
  const cfg = props.room.config
  for (let y = 0; y < cfg.map_height; y++) {
    for (let x = 0; x < cfg.map_width; x++) {
      const k = key(x, y)
      if (!props.visibleCells || props.visibleCells.has(k)) continue
      ctx.fillStyle = (props.exploredCells?.has(k) ?? false)
        ? 'rgba(40, 40, 40, 0.55)'
        : '#111'
      ctx.fillRect(x * CELL, y * CELL, CELL, CELL)
    }
  }
}

/* ================================================================
   Token 层 — 在所有视觉遮罩之上
   ================================================================ */
function drawTokens(ctx: CanvasRenderingContext2D) {
  for (const t of Object.values(props.room.tokens)) {
    if (!t.position) continue
    const tkSize = t.size || 1
    const isSelf = t.owner_id === props.selfTokenId
    const isDead = t.is_dead
    const isVisible = !props.visibleCells || props.visibleCells.has(key(t.position.x, t.position.y))
    if (!isSelf && !isVisible) continue

    const cx = t.position.x * CELL + (CELL * tkSize) / 2
    const cy = t.position.y * CELL + (CELL * tkSize) / 2
    const isSelected = t.id === selectedTokenId.value

    if (isSelected) {
      ctx.strokeStyle = '#0f0'; ctx.lineWidth = 3
      ctx.strokeRect(t.position.x * CELL - 1, t.position.y * CELL - 1, CELL * tkSize + 2, CELL * tkSize + 2)
    }

    const avatarImg = t.avatar_url ? avatarCache.value[t.avatar_url] : null
    const r = (CELL / 2.5) * tkSize
    if (avatarImg && avatarImg.complete) {
      ctx.save()
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.clip()
      ctx.drawImage(avatarImg, cx - r, cy - r, r * 2, r * 2)
      ctx.restore()
      ctx.strokeStyle = isDead ? '#888' : (isSelf ? '#fa0' : (t.type === 'monster' ? '#c33' : '#3a7'))
      ctx.lineWidth = 2
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke()
    } else {
      ctx.fillStyle = isDead ? '#888' : (isSelf ? '#fa0' : (t.type === 'monster' ? '#c33' : '#3a7'))
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill()
    }

    if (props.combatMode === 'attack' && !isSelf && !isDead && t.owner_id !== props.selfTokenId) {
      ctx.strokeStyle = '#f00'; ctx.lineWidth = 3; ctx.setLineDash([4, 2])
      ctx.beginPath(); ctx.arc(cx, cy, (CELL * tkSize) / 2 + 2, 0, Math.PI * 2); ctx.stroke()
      ctx.setLineDash([])
    }

    const dirs = [[0, -1], [1, -1], [1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1]]
    const [fdx, fdy] = dirs[t.facing] || [0, -1]
    ctx.strokeStyle = '#fff'; ctx.lineWidth = 2
    ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + fdx * (CELL * tkSize) / 2, cy + fdy * (CELL * tkSize) / 2); ctx.stroke()

    if (!isDead) {
      const barW = CELL * tkSize - 4
      ctx.fillStyle = '#600'; ctx.fillRect(t.position.x * CELL + 2, t.position.y * CELL + CELL * tkSize - 5, barW, 3)
      const hpRatio = Math.max(0, t.hp / Math.max(1, t.max_hp))
      ctx.fillStyle = hpRatio > 0.5 ? '#3a7' : (hpRatio > 0.25 ? '#fa0' : '#c33')
      ctx.fillRect(t.position.x * CELL + 2, t.position.y * CELL + CELL * tkSize - 5, barW * hpRatio, 3)
    }

    if (!isDead && t.states && t.states.length > 0) {
      const badgeR = 5
      const startX = t.position.x * CELL + CELL * tkSize - badgeR - 2
      const startY = t.position.y * CELL + badgeR + 2
      const maxBadges = Math.min(t.states.length, 4)
      for (let si = 0; si < maxBadges; si++) {
        const s = t.states[si]
        const bx = startX - si * (badgeR * 2 + 1)
        const colorMap: Record<string, string> = {
          '点燃': '#e80', '中毒': '#a0f', '流血': '#c00',
          '撕裂': '#d40', '隐身': '#0aa', '护甲降低': '#666',
          '定身': '#48f', '沉默': '#f48', '毒圈': '#840',
        }
        const color = colorMap[s.name] || '#888'
        ctx.fillStyle = color
        ctx.beginPath(); ctx.arc(bx, startY, badgeR, 0, Math.PI * 2); ctx.fill()
        ctx.strokeStyle = 'rgba(255,255,255,0.5)'; ctx.lineWidth = 1; ctx.stroke()
        ctx.fillStyle = '#fff'
        ctx.font = `bold ${badgeR + 3}px sans-serif`
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
        ctx.fillText(s.name.charAt(0), bx, startY + 0.5)
        if (s.ttl > 0) {
          ctx.fillStyle = 'rgba(255,255,255,0.9)'
          ctx.font = 'bold 7px sans-serif'
          ctx.textAlign = 'center'
          ctx.fillText(String(s.ttl), bx, startY + badgeR + 6)
        }
      }
    }
  }
}

function drawTerrainPaintPreview(ctx: CanvasRenderingContext2D) {
  if (!props.terrainBrush || terrainPaintPreview.value.length === 0) return
  const brush = props.terrainBrush
  const colorMap: Record<string, string> = {
    wall: 'rgba(68,68,68,0.5)', grass: 'rgba(153,204,153,0.5)',
    water: 'rgba(119,204,255,0.5)', high: 'rgba(221,170,102,0.5)',
    flat: 'rgba(240,240,240,0.5)',
  }
  ctx.fillStyle = colorMap[brush] || 'rgba(250,160,0,0.4)'
  for (const [px, py] of terrainPaintPreview.value) ctx.fillRect(px * CELL, py * CELL, CELL, CELL)
  ctx.strokeStyle = '#fa0'; ctx.lineWidth = 2
  for (const [px, py] of terrainPaintPreview.value) ctx.strokeRect(px * CELL + 1, py * CELL + 1, CELL - 2, CELL - 2)
}

function drawTerrainHover(ctx: CanvasRenderingContext2D) {
  const showHover = props.terrainBrush || ['measure', 'cone', 'line', 'sphere'].includes(tool.value)
  if (!hoveredCell.value || !showHover) return
  const [hx, hy] = hoveredCell.value
  ctx.strokeStyle = '#fa0'; ctx.lineWidth = 2
  ctx.strokeRect(hx * CELL, hy * CELL, CELL, CELL)
}

function drawAoeMarkers(ctx: CanvasRenderingContext2D) {
  const all = [...aoeMarkers.value]
  if (currentAoe.value) all.push(currentAoe.value)
  for (const m of all) drawAoe(ctx, m)
}

function drawStrokes_(ctx: CanvasRenderingContext2D) {
  for (const s of drawStrokes.value) drawStroke(ctx, s)
  if (currentStroke.value) drawStroke(ctx, currentStroke.value)
}

function drawPoisonCircle(ctx: CanvasRenderingContext2D) {
  const cfg = props.room.config
  const poisonCfg = props.room.game_map as any
  if (!poisonCfg || !poisonCfg.poison_circle_enabled) return
  const cx = (poisonCfg.poison_circle_center_x ?? cfg.map_width / 2) * CELL + CELL / 2
  const cy = (poisonCfg.poison_circle_center_y ?? cfg.map_height / 2) * CELL + CELL / 2
  const r = (poisonCfg.poison_circle_radius ?? 15) * CELL
  ctx.strokeStyle = 'rgba(200, 50, 50, 0.8)'
  ctx.lineWidth = 3
  ctx.setLineDash([8, 4])
  ctx.beginPath()
  ctx.arc(cx, cy, r, 0, Math.PI * 2)
  ctx.stroke()
  ctx.setLineDash([])
}

function drawDetectedMarkers(ctx: CanvasRenderingContext2D) {
  if (!props.detectedTokens) return
  const selfTok = Object.values(props.room.tokens).find((t) => t.id === props.selfTokenId)
  if (!selfTok?.position) return
  const cx = selfTok.position.x * CELL + CELL / 2
  const cy = selfTok.position.y * CELL + CELL / 2
  const dirVec: Record<string, [number, number]> = {
    '北': [0, -1], '东北': [1, -1], '东': [1, 0], '东南': [1, 1],
    '南': [0, 1], '西南': [-1, 1], '西': [-1, 0], '西北': [-1, -1],
  }
  for (const [_tid, dir] of Object.entries(props.detectedTokens)) {
    const v = dirVec[dir]
    if (!v) continue
    const ax = cx + v[0] * CELL * 1.2
    const ay = cy + v[1] * CELL * 1.2
    ctx.fillStyle = 'rgba(200,200,255,0.7)'
    ctx.beginPath(); ctx.arc(ax, ay, CELL / 3, 0, Math.PI * 2); ctx.fill()
    ctx.strokeStyle = '#aaf'; ctx.lineWidth = 1; ctx.stroke()
    ctx.fillStyle = '#335'; ctx.font = '12px sans-serif'
    ctx.fillText('?', ax - 3, ay + 4)
    ctx.fillStyle = '#aaf'; ctx.font = '9px sans-serif'
    ctx.fillText(dir, ax - 8, ay - CELL / 3)
  }
}

function drawDragPath(ctx: CanvasRenderingContext2D) {
  if (dragPath.value.length === 0) return
  ctx.strokeStyle = '#fa0'; ctx.lineWidth = 3; ctx.setLineDash([4, 2]); ctx.beginPath()
  const self = Object.values(props.room.tokens).find((t) => t.id === props.selfTokenId)
  if (self?.position) ctx.moveTo(self.position.x * CELL + CELL / 2, self.position.y * CELL + CELL / 2)
  for (const [x, y] of dragPath.value) ctx.lineTo(x * CELL + CELL / 2, y * CELL + CELL / 2)
  ctx.stroke(); ctx.setLineDash([])
}

// --- AOE 模板绘制 ---
function drawAoe(ctx: CanvasRenderingContext2D, m: AoeMarker) {
  const [sx, sy] = m.start
  const [ex, ey] = m.end
  const cx = sx * CELL + CELL / 2
  const cy = sy * CELL + CELL / 2
  const dx = ex - sx, dy = ey - sy
  const dist = Math.round(Math.hypot(dx, dy))  // 欧几里得距离
  const colors: Record<string, [string, string]> = {
    measure: ['rgba(250,160,0,0.2)', '#fa0'],
    sphere:  ['rgba(80,192,255,0.25)', '#40c0ff'],
    cone:    ['rgba(255,80,80,0.25)',  '#ff5050'],
    line:    ['rgba(255,255,80,0.25)', '#ffff50'],
  }
  const [fill, stroke] = colors[m.kind] || colors.measure
  ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth = 2

  if (m.kind === 'measure' || m.kind === 'sphere') {
    const radius = Math.max(0, dist) * CELL
    ctx.beginPath(); ctx.arc(cx, cy, radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke()
    // 距离文本
    ctx.fillStyle = '#fff'; ctx.font = '12px sans-serif'
    ctx.fillText(`${dist}格`, cx + radius + 4, cy)
  } else if (m.kind === 'cone') {
    // 扇形：以起点为圆心，半径=dist，角度为起→终方向 ±30°（共 60°）
    const radius = Math.max(1, dist) * CELL
    const angle = Math.atan2(ey - sy, ex - sx)
    const spread = Math.PI / 6  // 30° 每侧，共 60°
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.arc(cx, cy, radius, angle - spread, angle + spread)
    ctx.closePath(); ctx.fill(); ctx.stroke()
    ctx.fillStyle = '#fff'; ctx.font = '12px sans-serif'
    ctx.fillText(`${dist}格锥形`, cx + Math.cos(angle) * radius + 4, cy + Math.sin(angle) * radius)
  } else if (m.kind === 'line') {
    // 直线：粗细=1格，从起点到终点
    const angle = Math.atan2(ey - sy, ex - sx)
    const len = Math.hypot(dx, dy) * CELL
    const thick = CELL / 2
    ctx.save()
    ctx.translate(cx, cy); ctx.rotate(angle)
    ctx.fillRect(0, -thick / 2, len, thick)
    ctx.strokeRect(0, -thick / 2, len, thick)
    ctx.restore()
    ctx.fillStyle = '#fff'; ctx.font = '12px sans-serif'
    ctx.fillText(`${Math.max(Math.abs(dx), Math.abs(dy))}格直线`, ex * CELL + CELL / 2 + 4, ey * CELL + CELL / 2)
  }
}

// --- 手绘注释绘制 ---
function drawStroke(ctx: CanvasRenderingContext2D, s: DrawStroke) {
  if (s.points.length < 2) return
  ctx.strokeStyle = s.color; ctx.lineWidth = 3; ctx.lineJoin = 'round'; ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(s.points[0][0], s.points[0][1])
  for (let i = 1; i < s.points.length; i++) ctx.lineTo(s.points[i][0], s.points[i][1])
  ctx.stroke()
}

// --- drop handler: Actor / Character Sheet 拖拽到地图生成 Token ---
function onDrop(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()
  const raw = e.dataTransfer?.getData('application/json')
  if (!raw) {
    console.warn('[onDrop] no dataTransfer data', e.dataTransfer?.types)
    return
  }
  try {
    const data = JSON.parse(raw)
    console.log('[onDrop] received', data, 'clientX', e.clientX, 'clientY', e.clientY)
    const rect = scrollRef.value!.getBoundingClientRect()
    const wx = (e.clientX - rect.left - pan.value.x) / zoom.value
    const wy = (e.clientY - rect.top - pan.value.y) / zoom.value
    const x = Math.floor(wx / CELL)
    const y = Math.floor(wy / CELL)
    console.log('[onDrop] computed cell', x, y, 'rect', rect.left, rect.top)
    if (data.kind === 'actor') {
      emit('spawn-actor', { actor_id: data.actor_id, x, y })
    } else if (data.kind === 'character_sheet') {
      emit('spawn-sheet', { sheet: data.sheet, x, y })
    } else {
      console.warn('[onDrop] unknown kind', data.kind)
    }
  } catch (err) {
    console.error('[onDrop] parse error', err, 'raw:', raw)
  }
}

function getCell(e: MouseEvent | Touch): [number, number] {
  const sr = scrollRef.value!; const rect = sr.getBoundingClientRect()
  const sx = e.clientX - rect.left; const sy = e.clientY - rect.top
  const wx = (sx - pan.value.x) / zoom.value
  const wy = (sy - pan.value.y) / zoom.value
  return [Math.floor(wx / CELL), Math.floor(wy / CELL)]
}

// 查找点击位置上的棋子
function tokenAt(x: number, y: number) {
  return Object.values(props.room.tokens).find(
    (t) => t.position && t.position.x === x && t.position.y === y && !t.is_dead
  )
}

// --- mousedown ---
function onDown(e: MouseEvent) {
  const [x, y] = getCell(e)

  if (e.button === 1 || e.button === 2) { e.preventDefault(); startPan(e); return }
  if (e.button !== 0) return

  // 左键 + 地形笔刷 → 绘图（最高优先级，覆盖其他工具）
  if (e.button === 0 && props.terrainBrush) {
    terrainPaintStart.value = [x, y]
    terrainPaintQueue.value = []
    // single 模式：直接画；line/rect 模式：开始拖拽，松手时画
    if (terrainPaintMode.value === 'single') {
      paintCell(x, y)
    }
    return
  }

  // 测距/AOE 模板工具
  if (tool.value === 'measure' || tool.value === 'cone' ||
      tool.value === 'line' || tool.value === 'sphere') {
    measuring.value = true
    measureStart.value = [x, y]; measureEnd.value = [x, y]
    currentAoe.value = { kind: tool.value, start: [x, y], end: [x, y] }
    draw(); return
  }

  // 手绘工具
  if (tool.value === 'draw') {
    currentStroke.value = {
      points: [worldCoord(e)],
      color: DRAW_COLORS[drawColorIdx.value],
    }
    draw(); return
  }

  // 落子模式（无自己棋子时点空地落子）
  if (!props.selfTokenId && !props.isAdmin) {
    const tok = tokenAt(x, y)
    if (tok) { selectedTokenId.value = tok.id; emit('token-selected', tok) }
    else emit('cell-click', { x, y })
    return
  }

  // 管理员或玩家：左键 → 选中+拖拽（不显示径向菜单）
  const clicked = tokenAt(x, y)
  if (clicked) {
    // 点已选中的棋子 → 取消菜单，直接拖拽
    if (clicked.id === selectedTokenId.value) {
      showRadial.value = false
      dragging.value = true
      dragPath.value = [[clicked.position!.x, clicked.position!.y]]
      return
    }
    selectedTokenId.value = clicked.id
    emit('token-selected', clicked)
    showRadial.value = false
    dragging.value = true
    dragPath.value = [[clicked.position!.x, clicked.position!.y]]
    return
  }

  // 空白处：有选中且工具是选择 → 记录起点，用于区分单击取消 vs 拖动转向
  if (selectedTokenId.value && tool.value === 'select') {
    dragging.value = true
    dragPath.value = []  // 空路径表示尚未开始移动
    dragStartForCancel.value = [x, y]
    return
  }
  selectedTokenId.value = null
  showRadial.value = false
  startPan(e)
}

// --- 右键 → 径向菜单 ---
function onContextMenu(e: MouseEvent) {
  const [x, y] = getCell(e)
  const clicked = tokenAt(x, y)
  if (clicked) {
    selectedTokenId.value = clicked.id
    emit('token-selected', clicked)
    showRadial.value = true
    draw()
  } else {
    selectedTokenId.value = null
    showRadial.value = false
    draw()
  }
}

// --- mousemove ---
function onMouseMove(e: MouseEvent) {
  const [x, y] = getCell(e)
  hoveredCell.value = [x, y]

  if (panning.value) { doPan(e); return }

  if (measuring.value) {
    measureEnd.value = [x, y]
    if (currentAoe.value) currentAoe.value.end = [x, y]
    draw(); return
  }

  // 手绘中：累积世界坐标点
  if (tool.value === 'draw' && currentStroke.value && e.buttons === 1) {
    currentStroke.value.points.push(worldCoord(e))
    draw(); return
  }

  // 地形笔刷拖拽预览
  if (props.terrainBrush && terrainPaintStart.value && e.buttons === 1) {
    const [sx, sy] = terrainPaintStart.value
    if (terrainPaintMode.value === 'line') {
      terrainPaintPreview.value = bresenhamLine(sx, sy, x, y)
    } else if (terrainPaintMode.value === 'rect') {
      terrainPaintPreview.value = rectCells(sx, sy, x, y)
    } else {
      // single 模式：连续涂抹
      paintCell(x, y)
    }
    draw(); return
  }

  // 大小拖拽中：实时更新预览
  if (sizeDragging.value && selectedToken.value) {
    const delta = (sizeDragStartY.value - e.clientY) * 0.03
    const previewSize = Math.max(1, Math.min(4, Math.round(sizeDragStartVal.value + delta)))
    // 直接修改响应式对象预览（不持久化，mouseup 才 emit）
    ;(selectedToken.value as any).size = previewSize
    draw(); return
  }

  // 空白处单击 vs 拖动：路径为空且尚未移动 → 不处理
  if (dragging.value && dragPath.value.length === 0 && dragStartForCancel.value) {
    const [sx, sy] = dragStartForCancel.value
    if (x === sx && y === sy) { draw(); return }
    // 开始真正拖动 → 初始化路径
    dragPath.value = [[sx, sy]]
  }

  if (!dragging.value) { draw(); return }

  const clicked = selectedTokenId.value ? props.room.tokens[selectedTokenId.value] : null
  const last = dragPath.value[dragPath.value.length - 1]

  // 有棋子被选中，但不是在棋子上拖的 → 拖拽转向
  if (clicked && last) {
    const [lx, ly] = last
    if (lx !== clicked.position!.x || ly !== clicked.position!.y) {
      // 旋转模式：根据鼠标位置计算朝向
      const dx = x - clicked.position!.x
      const dy = y - clicked.position!.y
      if (dx !== 0 || dy !== 0) {
        const angle = Math.atan2(dy, dx) * (180 / Math.PI) + 90
        const facing = (Math.round(angle / 45) + 8) % 8
        emit('token-rotate', clicked.id, facing)
      }
      dragPath.value = [[x, y]]
      draw()
      return
    }
    // 起始点在棋子位置 → 初始化移动
  }

  // 自由拖动：构建路径
  const self = props.room.tokens[props.selfTokenId || '']
  const ref = last || (clicked?.position ? [clicked.position.x, clicked.position.y] as [number, number] : null) || (self?.position ? [self.position.x, self.position.y] as [number, number] : null)
  if (!ref) return
  if (x === ref[0] && y === ref[1]) return
  const newPath = manhattanPath(ref[0], ref[1], x, y)
  for (const p of newPath) {
    const ll = dragPath.value[dragPath.value.length - 1]
    if (!ll || ll[0] !== p[0] || ll[1] !== p[1]) dragPath.value.push(p)
  }
  draw()
}

// 鼠标事件 → 世界像素坐标（用于手绘）
function worldCoord(e: MouseEvent): [number, number] {
  const sr = scrollRef.value!; const rect = sr.getBoundingClientRect()
  const sx = e.clientX - rect.left
  const sy = e.clientY - rect.top
  return [(sx - pan.value.x) / zoom.value, (sy - pan.value.y) / zoom.value]
}

// 曼哈顿路径：从 (x1,y1) 到 (x2,y2)，逐格步进
function manhattanPath(x1: number, y1: number, x2: number, y2: number): [number, number][] {
  const path: [number, number][] = []
  let cx = x1, cy = y1
  while (cx !== x2 || cy !== y2) {
    const dx = x2 - cx, dy = y2 - cy
    // 交替走 X 和 Y，使路径更像对角线
    if (Math.abs(dx) >= Math.abs(dy) && cx !== x2) cx += Math.sign(dx)
    else if (cy !== y2) cy += Math.sign(dy)
    else if (cx !== x2) cx += Math.sign(dx)
    path.push([cx, cy])
  }
  return path
}

function paintCell(x: number, y: number) {
  const k = key(x, y)
  if (paintedCells.value.has(k)) return
  paintedCells.value.add(k)
  const brush = props.terrainBrush
  // 特殊笔刷：黑暗/光源/清除元数据
  if (brush === 'dark') {
    terrainPaintQueue.value.push({ x, y, type: 'meta', meta: { is_dark: true, darkness_strength: 0.7 } })
    return
  }
  if (brush === 'light') {
    terrainPaintQueue.value.push({ x, y, type: 'meta', meta: { light_radius: props.lightRadius ?? 3 } })
    return
  }
  if (brush === 'clear_meta') {
    terrainPaintQueue.value.push({ x, y, type: 'meta', meta: { is_dark: false, darkness_strength: 0.0, light_radius: 0 } })
    return
  }
  // 普通地形
  if (brush) {
    terrainPaintQueue.value.push({ x, y, type: brush })
  }
}

function flushTerrainPaint() {
  if (terrainPaintQueue.value.length === 0) return
  // 统一使用 paint_cells 协议（替代 set_terrain + set_cell_meta，deprecated 但保留后端支持）
  const cells = terrainPaintQueue.value.map(p => {
    const cell: any = { x: p.x, y: p.y }
    if (p.type !== 'meta') { cell.terrain = p.type }
    if (p.meta) Object.assign(cell, p.meta)
    return cell
  })
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'paint_cells', payload: { cells } }
  }))
  terrainPaintQueue.value = []
}

// --- mouseup ---
function onMouseUp(e?: MouseEvent) {
  if (panning.value) { panning.value = false; return }
  if (measuring.value) {
    measuring.value = false
    // 保留 AOE 标记（若有效）
    if (currentAoe.value &&
        (currentAoe.value.start[0] !== currentAoe.value.end[0] ||
         currentAoe.value.start[1] !== currentAoe.value.end[1])) {
      aoeMarkers.value.push(currentAoe.value)
    }
    currentAoe.value = null
    measureStart.value = null; measureEnd.value = null
    draw(); return
  }
  // 手绘结束：保留 stroke
  if (tool.value === 'draw' && currentStroke.value) {
    if (currentStroke.value.points.length >= 2) drawStrokes.value.push(currentStroke.value)
    currentStroke.value = null
    draw(); return
  }
  // 地形笔刷结束：line/rect 模式应用预览，single 模式批量发送
  if (props.terrainBrush && terrainPaintStart.value) {
    if (terrainPaintMode.value === 'line' || terrainPaintMode.value === 'rect') {
      // 将预览区域加入队列并发送
      for (const [px, py] of terrainPaintPreview.value) {
        paintCell(px, py)
      }
    }
    flushTerrainPaint()
    terrainPaintStart.value = null
    terrainPaintPreview.value = []
    paintedCells.value.clear()
    draw()
    return
  }
  // 大小拖拽结束
  if (sizeDragging.value && selectedToken.value) {
    sizeDragging.value = false
    const delta = (sizeDragStartY.value - (e as MouseEvent).clientY) * 0.03
    const newSize = Math.max(1, Math.min(4, Math.round(sizeDragStartVal.value + delta)))
    emit('token-size', selectedToken.value.id, newSize)
    draw(); return
  }

  // 空白处单击（路径为空 = 没有实际拖动）
  if (dragging.value && dragPath.value.length === 0 && dragStartForCancel.value) {
    const [cx, cy] = dragStartForCancel.value
    const sel = selectedTokenId.value ? props.room.tokens[selectedTokenId.value] : null
    const controllable = !!sel && (props.isAdmin || sel.id === props.selfTokenId)
    // 选中可控棋子时点击空格 → 点击移动（和拖拽移动等效，更直觉）
    if (sel?.position && controllable && (cx !== sel.position.x || cy !== sel.position.y)) {
      const steps = manhattanPath(sel.position.x, sel.position.y, cx, cy)
      if (steps.length) {
        emit('path-committed', steps)
        const lastS = steps[steps.length - 1]
        const prevS = steps[steps.length - 2] || [sel.position.x, sel.position.y]
        emit('token-rotate', sel.id, facingFromDelta(lastS[0] - prevS[0], lastS[1] - prevS[1]))
      }
      dragging.value = false
      dragStartForCancel.value = null
      draw(); return
    }
    // 否则：点空地取消选中
    selectedTokenId.value = null
    showRadial.value = false
    dragging.value = false
    dragStartForCancel.value = null
    draw(); return
  }

  if (dragging.value && dragPath.value.length > 0) {
    // 仅当路径有意义时才提交移动（>1个点表示实际移动，单点表示只是旋转）
    if (dragPath.value.length > 1) {
      emit('path-committed', dragPath.value)
      const last = dragPath.value[dragPath.value.length - 1]
      const prev = dragPath.value[dragPath.value.length - 2]
      const movedToken = selectedTokenId.value ? props.room.tokens[selectedTokenId.value] : null
      const self = props.room.tokens[props.selfTokenId || '']
      const target = movedToken || self
      if (target?.position) {
        const from = prev || [target.position.x, target.position.y]
        emit('token-rotate', target.id, facingFromDelta(last[0] - from[0], last[1] - from[1]))
      }
    }
  }
  dragging.value = false
  dragPath.value = []
  dragStartForCancel.value = null
  draw()
}

function facingFromDelta(dx: number, dy: number): number {
  const dirs = [[0,-1],[1,-1],[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1]]
  for (let i = 0; i < 8; i++) {
    if (dirs[i][0] === Math.sign(dx) && dirs[i][1] === Math.sign(dy)) return i
  }
  return 0
}

// --- 双击看角色卡 ---
function onDblClick(e: MouseEvent) {
  const [x, y] = getCell(e)
  const tok = tokenAt(x, y)
  if (tok) emit('token-dblclick', tok)
}

// --- 平移 ---
function startPan(e: MouseEvent) {
  panning.value = true
  panStart.value = { mx: e.clientX, my: e.clientY, px: pan.value.x, py: pan.value.y }
}
function doPan(e: MouseEvent) {
  pan.value.x = panStart.value.px + (e.clientX - panStart.value.mx)
  pan.value.y = panStart.value.py + (e.clientY - panStart.value.my)
}

// --- 缩放 ---
function onWheel(e: WheelEvent) {
  const sr = scrollRef.value!; const rect = sr.getBoundingClientRect()
  zoomBy(e.deltaY > 0 ? -0.1 : 0.1, e.clientX - rect.left, e.clientY - rect.top)
}
function zoomBy(delta: number, cx: number, cy: number) {
  const oldZoom = zoom.value
  const newZoom = Math.max(0.3, Math.min(3, oldZoom + delta))
  if (newZoom === oldZoom) return
  pan.value.x = cx - (cx - pan.value.x) * (newZoom / oldZoom)
  pan.value.y = cy - (cy - pan.value.y) * (newZoom / oldZoom)
  zoom.value = newZoom
}
function resetView() { pan.value = { x: 0, y: 0 }; zoom.value = 1 }

onMounted(draw)
onUnmounted(() => { panning.value = false; dragging.value = false; painting.value = false })
watch(() => props.room, draw, { deep: true })
watch(selectedTokenId, draw)
watch(() => [props.bgImage, props.bgOpacity], draw)

defineExpose({
  terrainPaintMode,
})
</script>

<style scoped>
.canvas-scroll { width: 100%; height: 100%; overflow: hidden; position: relative;
  cursor: grab; user-select: none; background: #2a2a2a; }
.canvas-scroll:active { cursor: grabbing; }
.canvas-scroll.drag-over { outline: 2px dashed #0a7; outline-offset: -4px; background: #1a3a2a; }
canvas { border: 1px solid #666; touch-action: none; display: block; }
.vp-hud { position: absolute; bottom: 8px; right: 8px; display: flex; gap: 4px;
  align-items: center; background: rgba(0,0,0,0.7); padding: 4px 8px; border-radius: 4px;
  color: #fff; font-size: 12px; z-index: 10; }
.vp-hud button { padding: 2px 8px; background: #444; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; font-size: 12px; }
.vp-hud button.active { background: #fa0; }
.vp-hud button:hover { background: #666; }
.vp-hud .sep { color: #888; margin: 0 2px; }
.vp-hud .paint-hint { color: #fa0; font-size: 11px; margin-left: 4px; white-space: nowrap; }
.vp-hud .color-pick { display: flex; gap: 2px; padding-left: 4px; }
.vp-hud .color-chip { width: 18px; height: 18px; padding: 0; border: 2px solid #555; border-radius: 50%; cursor: pointer; }
.vp-hud .color-chip.active { border-color: #fff; }

/* Radial menu */
.radial-menu { position: absolute; z-index: 12; transform: translate(-50%, -50%);
  display: flex; flex-direction: column; gap: 4px; pointer-events: none; }
.radial-btn { width: 48px; height: 48px; border-radius: 50%; border: 2px solid #fa0;
  background: rgba(0,0,0,0.85); color: #fff; font-size: 11px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.1s; pointer-events: auto; }
.radial-btn:hover { background: #fa0; transform: scale(1.1); }
.radial-btn.move { border-color: #3a7; }
.radial-btn.move:hover { background: #3a7; }
.radial-btn.attack { border-color: #c33; }
.radial-btn.attack:hover { background: #c33; }
.radial-btn.item { border-color: #0af; }
.radial-btn.item:hover { background: #0af; }
.radial-btn.info { border-color: #fa0; }
.radial-btn.info:hover { background: #fa0; }
.radial-btn.dismiss { border-color: #666; width: 32px; height: 32px; font-size: 14px; }
.radial-btn.dismiss:hover { background: #666; }

/* Scale drag handle */
.scale-handle { position: absolute; z-index: 11; color: #fa0; font-size: 18px;
  cursor: nwse-resize; text-shadow: 0 0 3px rgba(0,0,0,0.8); user-select: none; }
</style>
