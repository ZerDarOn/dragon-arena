<template>
  <div class="chat">
    <div class="tabs">
      <button v-for="c in visibleChannels" :key="c.key" @click="active = c.key"
              :class="{ active: active === c.key }">{{ c.label }}</button>
    </div>
    <div class="messages">
      <MessageBubble v-for="m in current" :key="m.id" :msg="m" />
      <p v-if="!current.length" class="empty">无消息</p>
    </div>
    <div class="input" v-if="active !== 'war_hall'">
      <input v-model="text" @keyup.enter="send" placeholder="说话..." />
      <button @click="send">发送</button>
      <label v-if="active === 'spatial'">
        <input type="checkbox" v-model="shout" />大喊
      </label>
    </div>
    <div class="input" v-else>
      <p class="readonly-hint">战争大厅为系统播报频道，仅管理员可发送</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useChatStore } from '../../stores/chat'
import MessageBubble from './MessageBubble.vue'

interface ChannelDef { key: string; label: string }

const props = defineProps<{
  /** Allowed channels in this view; defaults to global hall + private only (workbench mode). */
  channels?: string[]
}>()

const chat = useChatStore()
const active = ref('hall')
const text = ref('')
const shout = ref(false)

const ALL_CHANNELS: ChannelDef[] = [
  { key: 'hall', label: '大厅' },
  { key: 'private', label: '私聊' },
  { key: 'campaign_hall', label: '战役大厅' },
  { key: 'spatial', label: '空间' },
  { key: 'war_hall', label: '战争大厅' },
]

const visibleChannels = computed<ChannelDef[]>(() => {
  const allowed = props.channels ?? ['hall', 'private']
  return ALL_CHANNELS.filter((c) => allowed.includes(c.key))
})

const current = computed(() => {
  const key = active.value
  if (key === 'hall') return chat.hall
  if (key === 'campaign_hall') return chat.campaignHall
  if (key === 'war_hall') return chat.warHall
  if (key === 'spatial') return chat.inbox
  if (key === 'private') return chat.battle // placeholder for private DMs
  return []
})

function send() {
  if (!text.value) return
  let channel = active.value
  if (active.value === 'spatial') {
    channel = shout.value ? 'spatial_shout' : 'spatial_normal'
  }
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'chat', payload: { channel, text: text.value } },
  }))
  text.value = ''
}
</script>

<style scoped>
.chat { display: flex; flex-direction: column; height: 100%; font-family: sans-serif; }
.tabs button { padding: 4px 8px; } .tabs button.active { background: #fa0; color: #fff; }
.messages { flex: 1; overflow-y: auto; padding: 4px; }
.empty { color: #999; text-align: center; padding: 16px; font-size: 12px; }
.input { padding: 8px; border-top: 1px solid #ccc; display: flex; gap: 6px; align-items: center; }
.input input[type=text], .input input:not([type]) { flex: 1; padding: 4px; }
.readonly-hint { margin: 0; color: #999; font-size: 12px; }
</style>
