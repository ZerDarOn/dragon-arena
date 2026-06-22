import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage } from '../api/types'
import { useSelfStore } from './self'

export const useChatStore = defineStore('chat', () => {
  const hall = ref<ChatMessage[]>([])
  const battle = ref<ChatMessage[]>([])
  const privateChats = ref<Record<string, ChatMessage[]>>({})
  const inbox = ref<ChatMessage[]>([])
  const campaignHall = ref<ChatMessage[]>([])
  const warHall = ref<ChatMessage[]>([])

  function addMessage(msg: ChatMessage) {
    const self = useSelfStore()
    if (msg.channel === 'hall') hall.value.push(msg)
    else if (msg.channel === 'campaign_hall') campaignHall.value.push(msg)
    else if (msg.channel === 'war_hall') warHall.value.push(msg)
    else if (msg.channel === 'battle') battle.value.push(msg)
    else if (msg.channel === 'private') {
      const other = msg.sender_id === self.playerId
        ? (msg.recipients?.find((r) => r !== self.playerId) ?? '')
        : msg.sender_id
      ;(privateChats.value[other] ||= []).push(msg)
    } else if (msg.channel.startsWith('spatial')) inbox.value.push(msg)
  }
  return { hall, battle, privateChats, inbox, campaignHall, warHall, addMessage }
})
