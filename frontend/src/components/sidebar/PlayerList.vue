<template><div><h3>玩家</h3><ul>
  <li v-for="p in players" :key="p.id">{{ p.nickname || p.id }}
    <span v-if="p.is_host">[团主]</span><span v-if="!p.is_connected">[断线]</span></li>
</ul></div></template>
<script setup lang="ts">
import { computed } from 'vue'
import { useRoomStore } from '../../stores/room'
const room = useRoomStore()
const players = computed(() => Object.values(room.room.value?.players ?? {}))
</script>
