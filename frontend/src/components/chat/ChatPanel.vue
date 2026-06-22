<template><div class="chat">
<div class="tabs"><button v-for="c in channels" :key="c.key" @click="active = c.key" :class="{ active: active === c.key }">{{ c.label }}</button></div>
<div class="messages"><MessageBubble v-for="m in current" :key="m.id" :msg="m" /></div>
<div class="input"><input v-model="text" @keyup.enter="send" placeholder="说话..." /><button @click="send">发送</button>
<label><input type="checkbox" v-model="shout" />大喊</label></div>
</div></template>
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '../../stores/chat'
import MessageBubble from './MessageBubble.vue'
const chat = useChatStore()
const active = ref('hall'); const text = ref(''); const shout = ref(false)
const channels = [{ key: 'hall', label: '大厅' }, { key: 'spatial', label: '空间' }, { key: 'battle', label: '战斗' }]
const current = computed(() => active.value === 'hall' ? chat.hall : active.value === 'spatial' ? chat.inbox : chat.battle)
function send() {
  const channel = shout.value ? 'spatial_shout' : (active.value === 'spatial' ? 'spatial_normal' : active.value)
  window.dispatchEvent(new CustomEvent('ws-send', { detail: { type: 'chat', payload: { channel, text: text.value } } }))
  text.value = ''
}
</script>
<style scoped>
.chat { display: flex; flex-direction: column; height: 100%; font-family: sans-serif; }
.tabs button { padding: 4px 8px; } .tabs button.active { background: #fa0; color: #fff; }
.messages { flex: 1; overflow-y: auto; }
.input { padding: 8px; border-top: 1px solid #ccc; }
</style>
