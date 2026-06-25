// frontend/src/stores/chat.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage } from '../api/types'
import { useSelfStore } from './self'

export const useChatStore = defineStore('chat', () => {
  const hall = ref<ChatMessage[]>([])
  // "battle" 是后端 ChatService 真正认识的频道名（对应"战役大厅"标签）。
  // 之前前端单独发明了一个 "campaign_hall"，后端从来没认识过，消息发了就消失。
  const battle = ref<ChatMessage[]>([])
  const privateChats = ref<Record<string, ChatMessage[]>>({})
  const inbox = ref<ChatMessage[]>([])
  const warHall = ref<ChatMessage[]>([])

  function addMessage(msg: ChatMessage) {
    const self = useSelfStore()
    if (msg.channel === 'hall') hall.value.push(msg)
    else if (msg.channel === 'war_hall') warHall.value.push(msg)
    else if (msg.channel === 'battle') battle.value.push(msg)
    else if (msg.channel === 'private') {
      const other = msg.sender_id === self.playerId
        ? (msg.recipients?.find((r) => r !== self.playerId) ?? '')
        : msg.sender_id
      ;(privateChats.value[other] ||= []).push(msg)
    } else if (msg.channel.startsWith('spatial')) inbox.value.push(msg)
  }

  function getPrivateMessages(otherId: string): ChatMessage[] {
    return privateChats.value[otherId] || []
  }

  function getAllPrivatePartners(): string[] {
    return Object.keys(privateChats.value)
  }

  return { hall, battle, privateChats, inbox, warHall, addMessage, getPrivateMessages, getAllPrivatePartners }
})
