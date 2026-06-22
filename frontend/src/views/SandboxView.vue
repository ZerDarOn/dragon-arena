<template>
  <div class="sandbox">
    <div class="stage">
      <div class="logo">🐲</div>
      <h2>Dragon Arena</h2>
      <p class="tagline">等待团长发起战役...</p>
      <div class="hint" v-if="isAdmin">你是管理员，可点击上方「创建战役」开始一场新的游戏</div>
      <div class="hint" v-else>等待管理员创建战役，或通过「加入战役」进入房间号</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)
</script>

<style scoped>
.sandbox { display: flex; align-items: center; justify-content: center; height: 100%;
  background: radial-gradient(ellipse at center, #1a1a2e 0%, #0f0f1a 100%); color: #eee;
  font-family: sans-serif; overflow: hidden; }
.stage { text-align: center; }
.logo { font-size: 120px; animation: float 3s ease-in-out infinite; }
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-20px); }
}
h2 { margin: 12px 0 4px; font-size: 32px; letter-spacing: 2px; }
.tagline { margin: 0 0 24px; color: #aaa; font-size: 14px; }
.hint { color: #888; font-size: 12px; max-width: 320px; margin: 0 auto; }
</style>
