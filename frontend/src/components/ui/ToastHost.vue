<template>
  <div class="toast-host">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type">{{ t.text }}</div>
  </div>
</template>

<script setup lang="ts">
import { useToast } from '../../composables/useToast'
const { toasts } = useToast()
</script>

<style scoped>
.toast-host {
  position: fixed; top: 12px; right: 12px; z-index: 10000;
  display: flex; flex-direction: column; gap: 6px; max-width: 320px;
}
.toast {
  padding: 8px 12px; border-radius: 4px; font-size: 12px; color: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.25); animation: toast-in 0.15s ease-out;
}
.toast.error { background: #c0392b; }
.toast.warn { background: #d68910; }
.toast.info { background: #2471a3; }
@keyframes toast-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
