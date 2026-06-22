<template><div><h3>状态</h3>
<select v-model="tokenId"><option v-for="t in tokens" :key="t.id" :value="t.id">{{ t.id }}</option></select>
<ul><li v-for="s in states" :key="s.id">{{ s.name }}({{ s.ttl }}回合) - {{ s.description }}</li></ul>
<input v-model="name" placeholder="状态名" /><input v-model.number="ttl" type="number" placeholder="回合" />
<button @click="add">添加</button></div></template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoomStore } from '../../stores/room'
const room = useRoomStore()
const tokens = computed(() => Object.values(room.room?.tokens ?? {}))
const tokenId = ref(''); const name = ref(''); const ttl = ref(1)
const states = computed(() => room.room?.tokens[tokenId.value]?.states ?? [])
function add() { window.dispatchEvent(new CustomEvent('ws-send', { detail: { type: 'add_state', payload: { token_id: tokenId.value, name: name.value, description: '', ttl: ttl.value } } })) }
</script>
