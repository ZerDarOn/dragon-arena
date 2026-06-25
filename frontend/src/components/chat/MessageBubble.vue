<template>
  <div class="msg" :class="[msg.channel, msg.content_type]">
    <!-- 系统消息 -->
    <template v-if="msg.content_type === 'system'">
      <span class="system-text">{{ msg.text }}</span>
    </template>
    <!-- 骰子结果 -->
    <template v-else-if="msg.content_type === 'dice'">
      <span class="sender">{{ senderName }}</span>
      <span class="dice">🎲 {{ msg.text }}</span>
    </template>
    <!-- 空间语音（衰减提示） -->
    <template v-else-if="msg.channel.startsWith('spatial')">
      <span class="sender">{{ senderName }}</span>
      <span class="text spatial" :style="spatialStyle" v-html="renderText(msg.text)"></span>
      <span v-if="msg.extra?.distance" class="meta">{{ formatDistance(msg.extra) }}</span>
    </template>
    <!-- 普通消息 -->
    <template v-else>
      <span class="sender">{{ senderName }}</span>
      <span class="text" v-html="renderText(msg.text)"></span>
    </template>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '../../api/types'
import { useRoomStore } from '../../stores/room'
const props = defineProps<{ msg: ChatMessage }>()

const room = useRoomStore()
// sender_id 是 player_id（见后端 chat_service），从 room.players 解析为昵称展示。
const senderName = computed(() => {
  const p = room.room?.players?.[props.msg.sender_id]
  return p?.nickname || p?.name || props.msg.sender_id
})

const spatialStyle = computed(() => {
  const att = props.msg.extra?.attenuation
  if (att === undefined) return {}
  // 衰减越大，文字越淡、越小
  const opacity = 0.3 + att * 0.7
  const scale = 0.85 + att * 0.15
  return { opacity: String(opacity), transform: `scale(${scale})`, transformOrigin: 'left center' }
})

function formatDistance(extra: any) {
  if (!extra) return ''
  const dist = extra.distance
  const isShout = extra.is_shout
  if (dist === undefined) return ''
  return `${dist}格${isShout ? '·大喊' : ''}`
}

function renderText(text?: string) {
  if (!text) return ''
  const emojis: Record<string, string> = {
    ':)': '😊', ';)': '😉', ':(': '😢', ':D': '😄', ':P': '😛',
    '(d20)': '🎲d20', '(d6)': '🎲d6', '(heart)': '❤️', '(fire)': '🔥',
  }
  let html = text.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]!))
  for (const [k, v] of Object.entries(emojis)) {
    html = html.split(k).join(v)
  }
  html = html.replace(/@(\S+)/g, '<span class="mention">@$1</span>')
  return html
}
</script>
<style scoped>
.msg { padding: 4px 8px; border-bottom: 1px solid #eee; font-size: 13px; }
.sender { font-weight: bold; margin-right: 8px; color: #335; }
.text { color: #222; }
.text.spatial { display: inline-block; transition: all 0.3s; }
.system-text { color: #888; font-style: italic; font-size: 12px; }
.dice { color: #609; font-weight: bold; background: #f0e6ff; padding: 2px 6px; border-radius: 4px; }
.mention { color: #fa0; font-weight: bold; cursor: pointer; }
.meta { color: #999; font-size: 10px; margin-left: 6px; }
.spatial_normal { background: #fff7e6; }
.spatial_shout { background: #fff0f0; font-weight: bold; }
.battle { background: #e6f7ff; }
.system { background: #f5f5f5; text-align: center; }
.dice { background: #f0e6ff; }
</style>
