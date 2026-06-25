<template>
  <div class="dice-overlay" :class="{ active: visible }">
    <div class="dice-stage" id="dice-box-stage"></div>
    <p v-if="loading" class="hint">骰子加载中…</p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { pendingRequest, ensureDiceBox, rollGroupsPhysically, clearDiceBox } from '../../services/diceBoxBridge'

const visible = ref(false)
const loading = ref(false)
let hideTimer: ReturnType<typeof setTimeout> | null = null

watch(pendingRequest, async (req) => {
  if (!req) return
  if (hideTimer) { clearTimeout(hideTimer); hideTimer = null }
  visible.value = true
  loading.value = true
  try {
    await ensureDiceBox('#dice-box-stage')
    loading.value = false
    clearDiceBox()
    const values = await rollGroupsPhysically(req.groups)
    req.resolve(values)
  } catch (err) {
    loading.value = false
    req.reject(err)
  } finally {
    pendingRequest.value = null
    // 摇完之后留几秒让大家看清楚骰子最终摆出来的样子，再淡出
    hideTimer = setTimeout(() => { visible.value = false }, 2500)
  }
})
</script>

<style scoped>
.dice-overlay {
  position: fixed; inset: 0; z-index: 9000;
  display: flex; align-items: center; justify-content: center;
  pointer-events: none; opacity: 0; transition: opacity 0.25s ease;
}
.dice-overlay.active { opacity: 1; }
.dice-stage {
  width: min(70vw, 560px); height: min(50vh, 400px);
  background: rgba(10, 12, 20, 0.55); border-radius: 12px;
}
.hint {
  position: absolute; color: #fff; font-size: 13px;
  text-shadow: 0 1px 3px rgba(0,0,0,0.6);
}
</style>
