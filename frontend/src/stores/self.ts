import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useAuthStore } from './auth'

export const useSelfStore = defineStore('self', () => {
  const auth = useAuthStore()
  const playerId = computed(() => auth.user?.id ?? '')
  const nickname = computed(() => auth.user?.nickname ?? '')
  const isHost = computed(() => auth.isAdmin) // MVP: admin acts as host
  function init(_id: string, _nick: string) {
    // no-op: identity now derived from auth store
  }
  return { playerId, nickname, isHost, init }
})
