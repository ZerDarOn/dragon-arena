import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useSelfStore = defineStore('self', () => {
  const playerId = ref(''); const nickname = ref(''); const isHost = ref(false)
  function init(id: string, nick: string) { playerId.value = id; nickname.value = nick }
  return { playerId, nickname, isHost, init }
})
