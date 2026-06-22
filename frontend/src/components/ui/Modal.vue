<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal-body">
      <header>
        <h3>{{ title }}</h3>
        <button class="x" @click="$emit('close')">×</button>
      </header>
      <div class="content">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ title: string }>()
defineEmits<{ (e: 'close'): void }>()
</script>

<style scoped>
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.5); display: flex;
  align-items: center; justify-content: center; z-index: 100; }
.modal-body { background: #fff; border-radius: 6px; min-width: 360px; max-width: 90vw;
  max-height: 90vh; display: flex; flex-direction: column; }
header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px;
  border-bottom: 1px solid #eee; }
h3 { margin: 0; font-size: 16px; }
.x { background: transparent; border: none; font-size: 20px; cursor: pointer; color: #999; }
.content { padding: 16px; overflow-y: auto; }
input, textarea { padding: 6px; border: 1px solid #ccc; border-radius: 3px; font-size: 13px;
  width: 100%; box-sizing: border-box; margin-bottom: 8px; }
button { padding: 6px 12px; background: #0f3460; color: #fff; border: none; border-radius: 3px;
  cursor: pointer; font-size: 13px; }
.err { color: #c33; font-size: 12px; margin: 4px 0; }
</style>
