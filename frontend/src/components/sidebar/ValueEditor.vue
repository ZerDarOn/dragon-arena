<template><div><h3>修改数值</h3>
<select v-model="tokenId"><option v-for="t in tokens" :key="t.id" :value="t.id">{{ t.id }}</option></select>
<select v-model="field"><option value="hp">生命</option><option value="armor">护甲</option><option value="ap">AP</option><option value="gold">G</option><option value="score">积分</option></select>
<input type="number" v-model.number="delta" /><button @click="apply">应用</button></div></template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoomStore } from '../../stores/room'
const room = useRoomStore()
const tokens = computed(() => Object.values(room.room.value?.tokens ?? {}))
const tokenId = ref(''); const field = ref('hp'); const delta = ref(0)
function apply() { window.dispatchEvent(new CustomEvent('ws-send', { detail: { type: 'modify_value', payload: { token_id: tokenId.value, field: field.value, delta: delta.value } } })) }
</script>
