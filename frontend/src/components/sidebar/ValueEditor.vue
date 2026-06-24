<template>
  <div class="value-editor">
    <h3>修改数值 <span v-if="token" class="target">→ {{ token.id }}</span></h3>
    <select v-if="!token && isAdmin" v-model="tokenId">
      <option value="">选择目标...</option>
      <option v-for="t in tokens" :key="t.id" :value="t.id">{{ t.id }}</option>
    </select>
    <div class="row">
      <select v-model="field">
        <option value="hp">生命</option>
        <option value="armor">护甲</option>
        <option value="ap">AP</option>
        <option value="gold">金币</option>
        <option value="score">积分</option>
      </select>
      <input type="number" v-model.number="delta" placeholder="±N" />
      <button @click="apply">应用</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoomStore } from '../../stores/room'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{ token?: any }>()
const room = useRoomStore()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)
const tokens = computed(() => Object.values(room.room?.tokens ?? {}))
const tokenId = ref(props.token?.id ?? '')
const field = ref('hp')
const delta = ref(0)

const targetId = computed(() => props.token?.id ?? tokenId.value)

function apply() {
  if (!targetId.value) return
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'modify_value', payload: { token_id: targetId.value, field: field.value, delta: delta.value } },
  }))
  delta.value = 0
}
</script>

<style scoped>
.value-editor { font-size: 12px; }
h3 { margin: 0 0 6px; font-size: 13px; color: #0f3460; border-bottom: 1px solid #eee; padding-bottom: 4px; }
.target { color: #fa0; font-size: 11px; }
.row { display: flex; gap: 4px; }
select, input { padding: 4px; font-size: 12px; border: 1px solid #ccc; border-radius: 3px; }
button { padding: 4px 10px; background: #0f3460; color: #fff; border: none; border-radius: 3px; cursor: pointer; }
</style>
