<template><div><h3>投骰</h3>
<select v-model.number="sides"><option :value="4">D4</option><option :value="6">D6</option><option :value="8">D8</option><option :value="10">D10</option><option :value="12">D12</option><option :value="20">D20</option><option :value="100">D100</option></select>
<input type="number" v-model.number="modifier" placeholder="修正" />
<button @click="roll">投</button>
<p v-if="last">{{ last.value }}+{{ last.modifier }}={{ last.total }}<span v-if="last.crit_success"> 大成功!</span><span v-if="last.crit_fail"> 大失败!</span></p>
</div></template>
<script setup lang="ts">
import { ref } from 'vue'
import type { DiceResult } from '../../api/types'
const sides = ref(20); const modifier = ref(0); const last = ref<DiceResult | null>(null)
window.addEventListener('ws-dice-result', (e: any) => last.value = e.detail)
function roll() { window.dispatchEvent(new CustomEvent('ws-send', { detail: { type: 'dice_roll', payload: { sides: sides.value, modifier: modifier.value } } })) }
</script>
