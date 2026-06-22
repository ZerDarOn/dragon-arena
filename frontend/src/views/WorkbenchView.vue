<template>
  <div class="workbench">
    <header class="top-bar">
      <span class="welcome">欢迎，{{ auth.user?.nickname }}
        <span class="tag" :class="{ admin: auth.isAdmin }">{{ auth.isAdmin ? '管理员' : '玩家' }}</span>
      </span>
      <div class="actions">
        <button @click="showSheet = true">角色卡</button>
        <button v-if="auth.isAdmin" @click="showCreate = true">创建战役</button>
        <button @click="showJoin = true">加入战役</button>
        <button v-if="auth.isAdmin" @click="showUsers = true">用户管理</button>
        <button @click="onLogout">登出</button>
      </div>
    </header>

    <div class="body">
      <aside class="chat-pane">
        <ChatPanel :channels="['hall', 'private']" />
      </aside>
      <main class="stage-pane">
        <SandboxView />
      </main>
    </div>

    <!-- Modals -->
    <Modal v-if="showCreate" title="创建战役" @close="showCreate = false">
      <input v-model="newRoomName" placeholder="战役名称" />
      <button @click="doCreateRoom">创建</button>
      <p v-if="createError" class="err">{{ createError }}</p>
    </Modal>

    <Modal v-if="showJoin" title="加入战役" @close="showJoin = false">
      <input v-model="joinRoomId" placeholder="房间号" />
      <button @click="doJoin">进入</button>
      <p v-if="joinError" class="err">{{ joinError }}</p>
      <details>
        <summary>可用房间</summary>
        <ul>
          <li v-for="r in rooms" :key="r.id" @click="joinRoomId = r.id">
            {{ r.name }} ({{ r.id }}) - {{ Object.keys(r.players).length }}人
          </li>
        </ul>
      </details>
    </Modal>

    <Modal v-if="showSheet" title="我的角色卡" @close="showSheet = false">
      <CharacterSheetEditor />
    </Modal>

    <Modal v-if="showUsers && auth.isAdmin" title="用户管理（管理员）" @close="showUsers = false">
      <AdminUserPanel />
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { createRoom, listRooms, fetchMe } from '../api/rest'
import type { Room } from '../api/types'
import ChatPanel from '../components/chat/ChatPanel.vue'
import SandboxView from './SandboxView.vue'
import Modal from '../components/ui/Modal.vue'
import CharacterSheetEditor from '../components/sheets/CharacterSheetEditor.vue'
import AdminUserPanel from '../components/admin/AdminUserPanel.vue'

const router = useRouter()
const auth = useAuthStore()
const showCreate = ref(false); const showJoin = ref(false)
const showSheet = ref(false); const showUsers = ref(false)
const newRoomName = ref(''); const createError = ref('')
const joinRoomId = ref(''); const joinError = ref('')
const rooms = ref<Room[]>([])

async function refreshRooms() {
  try { rooms.value = await listRooms() } catch {}
}

async function doCreateRoom() {
  createError.value = ''
  if (!newRoomName.value) { createError.value = '请输入战役名'; return }
  try {
    const r = await createRoom(newRoomName.value)
    console.log('[workbench] room created, navigating to /battle/' + r.id)
    router.push(`/battle/${r.id}`)
  } catch (e: any) {
    console.error('[workbench] createRoom failed', e)
    createError.value = e.message || '创建失败'
  }
}

async function doJoin() {
  joinError.value = ''
  if (!joinRoomId.value) { joinError.value = '请输入房间号'; return }
  router.push(`/battle/${joinRoomId.value}`)
}

function onLogout() {
  auth.logout()
  router.push('/login')
}

onMounted(async () => {
  // Verify stored token is still valid
  try { await fetchMe() } catch {
    auth.logout()
    router.push('/login')
    return
  }
  await refreshRooms()
})
</script>

<style scoped>
.workbench { display: flex; flex-direction: column; height: 100vh; font-family: sans-serif; overflow: hidden; }
.top-bar { display: flex; justify-content: space-between; align-items: center; padding: 8px 16px;
  background: #222; color: #eee; }
.welcome { font-size: 14px; }
.tag { padding: 2px 6px; border-radius: 3px; font-size: 11px; background: #3a7; margin-left: 4px; }
.tag.admin { background: #fa0; }
.actions { display: flex; gap: 8px; }
.actions button { padding: 6px 12px; background: #444; color: #fff; border: none; border-radius: 3px; cursor: pointer; }
.actions button:hover { background: #555; }
.body { display: grid; grid-template-columns: 320px 1fr; flex: 1; min-height: 0; }
.chat-pane { border-right: 1px solid #444; min-height: 0; }
.stage-pane { min-height: 0; }
.err { color: #c33; font-size: 12px; margin: 8px 0; }
details { margin-top: 12px; }
summary { cursor: pointer; color: #888; font-size: 12px; }
details ul { list-style: none; padding: 0; }
details li { padding: 6px 0; border-bottom: 1px solid #eee; cursor: pointer; font-size: 13px; }
details li:hover { background: #f5f5f5; }

/* Modal slot content styles — needs :deep() to cross scoped boundary */
:deep(.modal-body input) { padding: 6px 8px; border: 1px solid #ccc; border-radius: 3px;
  font-size: 13px; width: 100%; box-sizing: border-box; margin-bottom: 8px; }
:deep(.modal-body button) { padding: 8px 16px; background: #0f3460; color: #fff; border: none;
  border-radius: 3px; cursor: pointer; font-size: 13px; }
:deep(.modal-body button:hover) { background: #1a4a7a; }

@media (max-width: 900px) {
  .body { grid-template-columns: 1fr; grid-template-rows: 200px 1fr; }
}
</style>
