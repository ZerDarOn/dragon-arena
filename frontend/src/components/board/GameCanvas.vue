<template>
  <canvas ref="canvasRef" @mousedown="onDown" @mousemove="onMove" @mouseup="onUp"
          @touchstart.prevent="onTouchStart" @touchmove.prevent="onTouchMove" @touchend.prevent="onUp" />
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { Room } from '../../api/types'

const props = defineProps<{
  room: Room
  selfTokenId?: string
  visibleCells?: Set<string>
  terrainBrush?: string
}>()
const emit = defineEmits<{ (e: 'path-committed', path: [number, number][]): void }>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const CELL = 32
const dragging = ref(false)
const dragPath = ref<[number, number][]>([])

function key(x: number, y: number) { return `${x},${y}` }

function draw() {
  const cv = canvasRef.value; if (!cv) return
  const ctx = cv.getContext('2d')!
  const cfg = props.room.config
  cv.width = cfg.map_width * CELL; cv.height = cfg.map_height * CELL
  ctx.clearRect(0, 0, cv.width, cv.height)
  for (let y = 0; y < cfg.map_height; y++) {
    for (let x = 0; x < cfg.map_width; x++) {
      const vis = !props.visibleCells || props.visibleCells.has(key(x, y))
      ctx.fillStyle = vis ? '#f0f0f0' : '#333'
      ctx.fillRect(x * CELL, y * CELL, CELL, CELL)
      ctx.strokeStyle = '#999'; ctx.strokeRect(x * CELL, y * CELL, CELL, CELL)
    }
  }
  for (const t of Object.values(props.room.tokens)) {
    if (!t.position) continue
    if (!props.visibleCells || props.visibleCells.has(key(t.position.x, t.position.y))) {
      const cx = t.position.x * CELL + CELL / 2
      const cy = t.position.y * CELL + CELL / 2
      ctx.fillStyle = t.is_dead ? '#888' : '#3a7'
      ctx.beginPath(); ctx.arc(cx, cy, CELL / 3, 0, Math.PI * 2); ctx.fill()
      const dirs = [[0,-1],[1,-1],[1,0],[1,1],[0,1],[-1,1],[-1,0],[-1,-1]]
      const [dx, dy] = dirs[t.facing]
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 2
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + dx * CELL / 2, cy + dy * CELL / 2); ctx.stroke()
    }
  }
  if (dragPath.value.length > 0) {
    ctx.strokeStyle = '#fa0'; ctx.lineWidth = 3; ctx.beginPath()
    const self = Object.values(props.room.tokens).find((t) => t.id === props.selfTokenId)
    if (self?.position) ctx.moveTo(self.position.x * CELL + CELL / 2, self.position.y * CELL + CELL / 2)
    for (const [x, y] of dragPath.value) ctx.lineTo(x * CELL + CELL / 2, y * CELL + CELL / 2)
    ctx.stroke()
  }
}

function getCell(e: MouseEvent | Touch): [number, number] {
  const cv = canvasRef.value!; const rect = cv.getBoundingClientRect()
  return [Math.floor((e.clientX - rect.left) * (cv.width / rect.width) / CELL),
          Math.floor((e.clientY - rect.top) * (cv.height / rect.height) / CELL)]
}

function onDown(e: MouseEvent) {
  const [x, y] = getCell(e)
  if (props.terrainBrush) {
    window.dispatchEvent(new CustomEvent('ws-send', {
      detail: { type: 'set_terrain', payload: { x, y, type: props.terrainBrush } }
    }))
    return
  }
  if (!props.selfTokenId) return
  const self = props.room.tokens[props.selfTokenId]
  if (self?.position && x === self.position.x && y === self.position.y) {
    dragging.value = true; dragPath.value = []
  }
}

function onMove(e: MouseEvent) {
  if (!dragging.value) return
  const [x, y] = getCell(e)
  const last = dragPath.value[dragPath.value.length - 1]
  let ref: [number, number] | null = last
  if (!ref) {
    const s = props.room.tokens[props.selfTokenId || '']
    if (s?.position) ref = [s.position.x, s.position.y]
  }
  if (!ref) return
  if (Math.max(Math.abs(x - ref[0]), Math.abs(y - ref[1])) !== 1) return
  if (!last || last[0] !== x || last[1] !== y) {
    dragPath.value.push([x, y]); draw()
  }
}

function onTouchStart(e: TouchEvent) { if (e.touches[0]) onDown(e.touches[0] as any) }
function onTouchMove(e: TouchEvent) { if (e.touches[0]) onMove(e.touches[0] as any) }

function onUp() {
  if (dragging.value && dragPath.value.length > 0) emit('path-committed', dragPath.value)
  dragging.value = false; dragPath.value = []; draw()
}

onMounted(draw)
watch(() => props.room, draw, { deep: true })
</script>

<style scoped>
canvas { border: 1px solid #666; max-width: 100%; touch-action: none; }
</style>
