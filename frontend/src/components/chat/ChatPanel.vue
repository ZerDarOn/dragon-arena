<template>
  <div class="chat">
    <div class="tabs">
      <button v-for="c in visibleChannels" :key="c.key" @click="switchChannel(c.key)"
              :class="{ active: activeTab === c.key }">
        {{ c.label }}
        <span v-if="unreadCounts[c.key]" class="badge">{{ unreadCounts[c.key] }}</span>
      </button>
      <!-- 私聊对象标签页 -->
      <button v-for="p in privateTabs" :key="p.id" @click="switchChannel('private', p.id)"
              :class="{ active: activeTab === 'private' && privateTarget === p.id }"
              class="private-tab">
        {{ p.name }}
        <span v-if="p.unread" class="badge">{{ p.unread }}</span>
        <span class="close" @click.stop="closePrivateTab(p.id)">×</span>
      </button>
    </div>
    <div class="messages">
      <MessageBubble v-for="m in currentMessages" :key="m.id" :msg="m" />
      <p v-if="!currentMessages.length" class="empty">无消息</p>
    </div>
    <div class="input" v-if="activeTab !== 'war_hall' || isAdmin">
      <select v-if="activeTab === 'private' && !privateTarget" v-model="privateTarget">
        <option value="">选择收件人...</option>
        <option v-for="p in allPlayers" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <input v-model="text" @keyup.enter="send" :placeholder="inputPlaceholder" />
      <button @click="send">发送</button>
      <label v-if="activeTab === 'spatial'">
        <input type="checkbox" v-model="shout" />大喊
      </label>
    </div>
    <div class="input" v-else>
      <p class="readonly-hint">战争大厅为系统播报频道，仅管理员可发送</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useChatStore } from '../../stores/chat'
import { useRoomStore } from '../../stores/room'
import { useAuthStore } from '../../stores/auth'
import MessageBubble from './MessageBubble.vue'

interface ChannelDef { key: string; label: string }

const props = defineProps<{
  channels?: string[]
}>()

const chat = useChatStore()
const room = useRoomStore()
const auth = useAuthStore()
const activeTab = ref('hall')
const text = ref('')
const shout = ref(false)
const privateTarget = ref('')

const isAdmin = computed(() => auth.isAdmin)

// 未读消息计数
const lastRead = ref<Record<string, number>>({})

const unreadCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const c of visibleChannels.value) {
    const msgs = getMessages(c.key)
    const last = lastRead.value[c.key] ?? 0
    counts[c.key] = msgs.filter((m: any) => m.timestamp > last).length
  }
  return counts
})

function getMessages(key: string) {
  if (key === 'hall') return chat.hall
  if (key === 'campaign_hall') return chat.campaignHall
  if (key === 'war_hall') return chat.warHall
  if (key === 'spatial') return chat.inbox
  if (key === 'private') {
    if (!privateTarget.value) return []
    return chat.getPrivateMessages(privateTarget.value)
  }
  return []
}

// 切换频道时标记已读
watch(activeTab, (key) => {
  lastRead.value[key] = Date.now()
})
watch(privateTarget, () => {
  if (activeTab.value === 'private' && privateTarget.value) {
    lastRead.value[`private:${privateTarget.value}`] = Date.now()
  }
})

// 新消息到来时，如果不在当前频道，自动计数
watch(() => chat.hall.length, () => { if (activeTab.value !== 'hall') {/* 已由 unreadCounts 自动计算 */} })
watch(() => chat.campaignHall.length, () => { if (activeTab.value !== 'campaign_hall') {} })
watch(() => chat.warHall.length, () => { if (activeTab.value !== 'war_hall') {} })
watch(() => chat.inbox.length, () => { if (activeTab.value !== 'spatial') {} })
watch(() => chat.privateChats, () => {
  // 私聊未读由 privateTabs 计算
}, { deep: true })

const ALL_CHANNELS: ChannelDef[] = [
  { key: 'hall', label: '大厅' },
  { key: 'private', label: '私聊' },
  { key: 'campaign_hall', label: '战役大厅' },
  { key: 'spatial', label: '空间' },
  { key: 'war_hall', label: '战争大厅' },
]

// 所有玩家（包括离线）用于私聊收件人选择
const allPlayers = computed(() => {
  const r = room.room
  if (!r) return []
  return Object.values(r.players).map((p: any) => ({
    id: p.id,
    name: p.nickname || p.name || p.id,
  }))
})

// 私聊标签页：有聊天记录的 + 当前选中的
const privateTabs = computed(() => {
  const partners = new Set<string>(chat.getAllPrivatePartners())
  if (privateTarget.value) partners.add(privateTarget.value)
  return Array.from(partners).map(id => {
    const msgs = chat.getPrivateMessages(id)
    const lastReadTime = lastRead.value[`private:${id}`] ?? 0
    const unread = msgs.filter((m: any) => m.timestamp > lastReadTime).length
    const player = room.room?.players[id]
    return { id, name: player?.nickname || player?.name || id, unread }
  })
})

const inputPlaceholder = computed(() => {
  if (activeTab.value === 'private') return privateTarget.value ? '对TA私聊...' : '请先选择收件人'
  return '说话...'
})

const visibleChannels = computed<ChannelDef[]>(() => {
  const allowed = props.channels ?? ['hall', 'private']
  return ALL_CHANNELS.filter((c) => allowed.includes(c.key))
})

const currentMessages = computed(() => {
  const key = activeTab.value
  if (key === 'hall') return chat.hall
  if (key === 'campaign_hall') return chat.campaignHall
  if (key === 'war_hall') return chat.warHall
  if (key === 'spatial') return chat.inbox
  if (key === 'private') {
    if (!privateTarget.value) return []
    return chat.getPrivateMessages(privateTarget.value)
  }
  return []
})

function switchChannel(key: string, target?: string) {
  activeTab.value = key
  if (key === 'private' && target) {
    privateTarget.value = target
  }
  if (key !== 'private') {
    privateTarget.value = ''
  }
}

function closePrivateTab(id: string) {
  // 只是关闭标签页，不删除记录
  if (privateTarget.value === id) {
    privateTarget.value = ''
    activeTab.value = 'hall'
  }
}

function send() {
  if (!text.value) return
  let channel = activeTab.value
  let target_player: string | undefined
  if (activeTab.value === 'spatial') {
    channel = shout.value ? 'spatial_shout' : 'spatial_normal'
  }
  if (activeTab.value === 'private') {
    if (!privateTarget.value) return
    target_player = privateTarget.value
  }
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: { type: 'chat', payload: { channel, text: text.value, target_player } },
  }))
  text.value = ''
}
</script>

<style scoped>
.chat { display: flex; flex-direction: column; height: 100%; font-family: sans-serif; }
.tabs { display: flex; gap: 2px; overflow-x: auto; border-bottom: 1px solid #ddd; padding: 2px; }
.tabs button { padding: 4px 8px; white-space: nowrap; border: none; background: #f5f5f5; cursor: pointer; font-size: 12px; }
.tabs button.active { background: #fa0; color: #fff; }
.tabs button.private-tab { background: #e8f0ff; position: relative; padding-right: 18px; }
.tabs button.private-tab.active { background: #0a7; color: #fff; }
.tabs button .close { position: absolute; right: 2px; top: 2px; font-size: 10px; color: #999; cursor: pointer; }
.tabs button .close:hover { color: #c33; }
.messages { flex: 1; overflow-y: auto; padding: 4px; }
.empty { color: #999; text-align: center; padding: 16px; font-size: 12px; }
.input { padding: 8px; border-top: 1px solid #ccc; display: flex; gap: 6px; align-items: center; }
.input input[type=text], .input input:not([type]) { flex: 1; padding: 4px; }
.readonly-hint { margin: 0; color: #999; font-size: 12px; }
.badge { background: #c33; color: #fff; font-size: 10px; padding: 1px 4px; border-radius: 8px; margin-left: 4px; }
</style>
