<template>
  <div class="lobby">
    <h1>龙王争霸赛</h1>
    <div>
      <h2>创建房间</h2>
      <input v-model="roomName" placeholder="房间名" />
      <input v-model="nickname" placeholder="昵称" />
      <button @click="createRoom">创建</button>
    </div>
    <div v-if="rooms.length">
      <h2>加入房间</h2>
      <ul>
        <li v-for="r in rooms" :key="r.id">
          {{ r.name }} ({{ Object.keys(r.players).length }}人)
          <input v-model="joinNick[r.id]" placeholder="昵称" />
          <button @click="joinRoom(r.id)">加入</button>
        </li>
      </ul>
    </div>
    <button @click="refresh">刷新</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useSelfStore } from '../stores/self'
import type { Room } from '../api/types'

const API = 'http://localhost:8000'
const router = useRouter()
const self = useSelfStore()
const roomName = ref(''); const nickname = ref('')
const rooms = ref<Room[]>([])
const joinNick = reactive<Record<string, string>>({})

async function refresh() { rooms.value = await (await fetch(`${API}/rooms`)).json() }
async function createRoom() {
  const pid = 'p_' + Math.random().toString(36).slice(2, 8)
  const r = await fetch(`${API}/rooms`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: roomName.value, host_id: pid }),
  })
  const room = await r.json()
  self.init(pid, nickname.value); self.isHost = true
  router.push(`/room/${room.id}`)
}
async function joinRoom(roomId: string) {
  const pid = 'p_' + Math.random().toString(36).slice(2, 8)
  self.init(pid, joinNick[roomId] || 'Player')
  router.push(`/room/${roomId}`)
}
onMounted(refresh)
</script>

<style scoped>
.lobby { max-width: 600px; margin: 40px auto; padding: 20px; font-family: sans-serif; }
input { margin: 0 8px 8px 0; padding: 4px; }
button { padding: 4px 12px; cursor: pointer; }
ul { list-style: none; padding: 0; }
li { padding: 8px 0; border-bottom: 1px solid #eee; }
</style>
