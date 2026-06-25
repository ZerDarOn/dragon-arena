<template>
  <router-view />
  <ToastHost />
  <DiceBoxOverlay />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import ToastHost from './components/ui/ToastHost.vue'
import DiceBoxOverlay from './components/ui/DiceBoxOverlay.vue'

// 预加载 dice-box-threejs：进入房间前利用浏览器空闲时间提前拉取 3D 引擎，
// 首次摇骰时不再出现"骰子加载中…"的等待。只加载不初始化，不影响性能。
onMounted(() => {
  const preload = () => import('@3d-dice/dice-box-threejs')
  if ('requestIdleCallback' in window) {
    (window as any).requestIdleCallback(preload, { timeout: 3000 })
  } else {
    setTimeout(preload, 2000)
  }
})
</script>
