<template><div><h3>行动轴 {{ room.room?.big_turn }}-{{ room.room?.sub_turn }}</h3>
<ol><li v-for="tid in room.room?.turn_order" :key="tid" :class="{ active: tid === room.room?.current_actor }">{{ tid }}</li></ol>
<button v-if="isCurrentActor" @click="endTurn">结束回合</button></div></template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRoomStore } from '../../stores/room'
import { useSelfStore } from '../../stores/self'
const room = useRoomStore(); const self = useSelfStore()
const isCurrentActor = computed(() => room.room?.players[self.playerId]?.token_id === room.room?.current_actor)
function endTurn() { window.dispatchEvent(new CustomEvent('ws-send', { detail: { type: 'end_turn', payload: {} } })) }
</script>
<style scoped>.active { font-weight: bold; color: #fa0; }</style>
