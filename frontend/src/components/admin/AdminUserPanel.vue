<template>
  <div class="admin-users">
    <h4>现有用户</h4>
    <ul>
      <li v-for="u in users" :key="u.id">
        <span>{{ u.nickname }}</span>
        <span :class="['tag', { admin: u.is_admin }]">{{ u.is_admin ? '管理员' : '玩家' }}</span>
        <button v-if="u.id !== currentId" class="del" @click="onDelete(u)">删</button>
        <span v-else class="self">（你）</span>
      </li>
    </ul>

    <h4>新建用户</h4>
    <input v-model="newNick" placeholder="用户名" />
    <input v-model="newPass" type="password" placeholder="密码" />
    <label><input type="checkbox" v-model="newIsAdmin" /> 管理员</label>
    <button @click="onCreate">创建</button>
    <p v-if="error" class="err">{{ error }}</p>
    <p v-if="ok" class="ok">已创建</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { adminListUsers, adminCreateUser, adminDeleteUser } from '../../api/rest'
import { useAuthStore } from '../../stores/auth'
import type { UserPublic } from '../../api/types'

const auth = useAuthStore()
const users = ref<UserPublic[]>([])
const newNick = ref(''); const newPass = ref(''); const newIsAdmin = ref(false)
const error = ref(''); const ok = ref(false)
const currentId = computed(() => auth.user?.id)

async function load() {
  try { users.value = await adminListUsers() } catch (e: any) { error.value = e.message }
}

async function onCreate() {
  error.value = ''; ok.value = false
  if (!newNick.value || !newPass.value) { error.value = '请填写完整'; return }
  try {
    await adminCreateUser(newNick.value, newPass.value, newIsAdmin.value)
    ok.value = true
    newNick.value = ''; newPass.value = ''; newIsAdmin.value = false
    await load()
  } catch (e: any) { error.value = e.message }
}

async function onDelete(u: UserPublic) {
  if (!confirm(`确定删除用户「${u.nickname}」？此操作会一并删除其所有角色卡。`)) return
  try { await adminDeleteUser(u.id); await load() }
  catch (e: any) { error.value = e.message }
}

onMounted(load)
</script>

<style scoped>
.admin-users { font-size: 13px; }
h4 { margin: 12px 0 6px; font-size: 13px; color: #666; }
ul { list-style: none; padding: 0; margin: 0 0 12px; }
li { display: flex; gap: 8px; align-items: center; padding: 4px 0; border-bottom: 1px solid #eee; }
li > span:first-child { flex: 1; }
.tag { padding: 2px 6px; border-radius: 2px; font-size: 11px; background: #3a7; color: #fff; }
.tag.admin { background: #fa0; }
.self { color: #999; font-size: 11px; }
.del { background: #c33; color: #fff; border: none; padding: 2px 6px; border-radius: 2px; cursor: pointer; }
input[type=text], input:not([type=checkbox]):not([type=radio]) { padding: 6px; border: 1px solid #ccc;
  border-radius: 3px; margin-right: 8px; }
.err { color: #c33; } .ok { color: #3a7; }
</style>
