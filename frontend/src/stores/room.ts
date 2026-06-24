import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Room } from '../api/types'

export const useRoomStore = defineStore('room', () => {
  const room = ref<Room | null>(null)
  function setState(payload: Room) { room.value = payload }
  function clear() { room.value = null }
  return { room, setState, clear }
})
