<template><div class="dm"><h3>团主工具</h3>
<div><button v-for="t in types" :key="t.v" @click="selected = t.v" :class="{ active: selected === t.v }">{{ t.l }}</button></div>
<p>点击地图设置地形</p></div></template>
<script setup lang="ts">
import { ref } from 'vue'
const selected = ref('')
const types = [{ v: '', l: '关闭' }, { v: 'flat', l: '平地' }, { v: 'wall', l: '墙' }, { v: 'grass', l: '草丛' }, { v: 'water', l: '水' }, { v: 'high', l: '高地' }]
defineExpose({ selected })
</script>
<style scoped>.dm { padding: 8px; background: #f5f5f5; border-bottom: 1px solid #ccc; }
button { padding: 4px 8px; margin-right: 4px; } button.active { background: #fa0; color: #fff; }</style>
