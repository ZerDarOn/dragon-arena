<template>
  <div class="dice-overlay" :class="{ active: visible }" @click="skip">
    <!-- 3D 舞台：标准骰子（d2/d4/d6/d8/d10/d12/d20）走物理动画 -->
    <div v-show="mode === '3d'" class="dice-stage" id="dice-box-stage"></div>

    <!-- 2D 揭示：没有 3D 模型的骰子（d100/d7/d5/d3…）用数字翻牌兜底 -->
    <div v-show="mode === '2d'" class="dice-2d">
      <div class="chips">
        <span v-for="(d, i) in twoDDice" :key="i" class="chip"
              :style="{ animationDelay: i * 70 + 'ms' }">
          <small>d{{ d.sides }}</small>{{ d.value }}
        </span>
      </div>
    </div>

    <p v-if="loading" class="hint">骰子加载中…</p>
    <p v-if="visible" class="skip-hint">点击跳过</p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import {
  pendingRoll, canAnimate, buildNotation, ensureDiceBox, animateRoll,
  type DieValue,
} from '../../services/diceBoxBridge'

const visible = ref(false)
const loading = ref(false)
const mode = ref<'3d' | '2d'>('3d')
const twoDDice = ref<DieValue[]>([])
let hideTimer: ReturnType<typeof setTimeout> | null = null
let activeResolve: (() => void) | null = null

function finish() {
  if (activeResolve) { const r = activeResolve; activeResolve = null; r() }
}

// 点击任意处跳过当前展示——快节奏对局里没人想每掷都等满动画。
function skip() {
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
  finish()
  visible.value = false
}

watch(pendingRoll, async (req) => {
  if (!req) return
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
  activeResolve = req.resolve
  visible.value = true

  if (canAnimate(req.dice)) {
    mode.value = '3d'
    loading.value = true
    try {
      await ensureDiceBox('#dice-box-stage')
      loading.value = false
      await animateRoll(buildNotation(req.dice))
    } catch {
      // 3D 失败（引擎没加载出来等）→ 退回 2D，别把请求方卡住
      loading.value = false
      mode.value = '2d'
      twoDDice.value = req.dice
      await new Promise((r) => setTimeout(r, 700))
    }
  } else {
    mode.value = '2d'
    twoDDice.value = req.dice
    await new Promise((r) => setTimeout(r, 900))
  }

  finish()
  pendingRoll.value = null
  // 摇完留一小会儿看清结果再淡出（3D 比 2D 多留一点）
  hideTimer = setTimeout(() => { visible.value = false }, mode.value === '3d' ? 1400 : 700)
})
</script>

<style scoped>
.dice-overlay {
  position: fixed; inset: 0; z-index: 9000;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none; opacity: 0; transition: opacity 0.2s ease;
}
.dice-overlay.active { opacity: 1; pointer-events: auto; cursor: pointer; }

.dice-stage {
  /* 适中尺寸：比原来 90vw×70vh 小很多 → 渲染像素更少、更省、也不至于整屏遮挡。
     position:relative 让内部 canvas 撑满此容器。 */
  position: relative;
  width: 60vw; height: 52vh; max-width: 760px; max-height: 560px;
  background: radial-gradient(ellipse at center, rgba(20, 24, 38, 0.6) 0%, rgba(8, 10, 18, 0.45) 100%);
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.06);
  overflow: hidden;
}
/* dice-box-threejs 把 three.js 的 <canvas> 直接挂进容器，按 clientWidth/Height 设尺寸 */
.dice-stage :deep(canvas) {
  width: 100% !important;
  height: 100% !important;
  display: block;
}

/* 2D 数字揭示 */
.dice-2d {
  display: flex; align-items: center; justify-content: center;
  padding: 28px 36px; border-radius: 16px;
  background: radial-gradient(ellipse at center, rgba(20, 24, 38, 0.85) 0%, rgba(8, 10, 18, 0.8) 100%);
  border: 1px solid rgba(255,255,255,0.08);
}
.chips { display: flex; gap: 12px; flex-wrap: wrap; max-width: 70vw; justify-content: center; }
.chip {
  position: relative;
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 64px; height: 64px; padding: 0 10px;
  font-size: 30px; font-weight: 800; color: #fff;
  background: linear-gradient(160deg, #2a4a8a, #15294f);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.45);
  animation: flip 0.5s cubic-bezier(0.2, 0.9, 0.3, 1.2) both;
}
.chip small {
  position: absolute; top: 4px; left: 6px;
  font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.55);
}
@keyframes flip {
  0%   { transform: rotateX(-90deg) scale(0.7); opacity: 0; }
  100% { transform: rotateX(0) scale(1); opacity: 1; }
}

.hint, .skip-hint {
  position: absolute; color: #fff;
  text-shadow: 0 1px 3px rgba(0,0,0,0.7);
}
.hint { font-size: 13px; }
.skip-hint {
  bottom: 6%; font-size: 12px; color: rgba(255,255,255,0.55); letter-spacing: 1px;
}
</style>
