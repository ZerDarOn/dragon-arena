<template>
  <div class="login-page">
    <div class="card">
      <h1>龙王争霸赛</h1>
      <p class="hint">登录后进入工作台</p>

      <div v-if="history.length" class="history">
        <h3>最近登录</h3>
        <ul>
          <li v-for="h in history" :key="h.nickname" @click="selectHistory(h)">
            <span class="nick">{{ h.nickname }}</span>
            <span :class="['tag', h.role]">{{ h.role === 'admin' ? '管理员' : '玩家' }}</span>
            <button class="x" @click.stop="removeHistory(h.nickname)">×</button>
          </li>
        </ul>
      </div>

      <form @submit.prevent="onLogin">
        <input v-model="nickname" placeholder="用户名" autocomplete="username" />
        <input v-model="password" type="password" placeholder="密码" autocomplete="current-password" />
        <p v-if="error" class="err">{{ error }}</p>
        <button type="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
      </form>

      <details class="hint-default">
        <summary>首次使用？</summary>
        <p>后端首次启动会自动创建默认管理员账号：</p>
        <p><code>admin</code> / <code>admin123</code></p>
        <p class="warn">登录后请立即在「用户管理」中修改或新建账号。</p>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore, type LoginHistoryEntry } from '../stores/auth'
import { login as apiLogin } from '../api/rest'

const router = useRouter()
const auth = useAuthStore()
const { history } = storeToRefs(auth)
const nickname = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

function selectHistory(h: LoginHistoryEntry) {
  nickname.value = h.nickname
  password.value = ''
  error.value = ''
}

function removeHistory(nick: string) {
  auth.removeHistory(nick)
}

async function onLogin() {
  if (!nickname.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const data = await apiLogin(nickname.value, password.value)
    auth.setSession(data)
    router.push('/main')
  } catch (e: any) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page { display: flex; align-items: center; justify-content: center; min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); font-family: sans-serif; }
.card { background: #fff; padding: 32px 40px; border-radius: 8px; min-width: 320px; max-width: 400px; }
h1 { margin: 0 0 8px; font-size: 24px; color: #333; }
.hint { margin: 0 0 16px; color: #666; font-size: 13px; }
.history { margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px dashed #ddd; }
.history h3 { margin: 0 0 8px; font-size: 13px; color: #888; font-weight: normal; }
.history ul { list-style: none; padding: 0; margin: 0; }
.history li { display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 4px;
  cursor: pointer; font-size: 14px; }
.history li:hover { background: #f0f0f0; }
.nick { flex: 1; }
.tag { padding: 2px 6px; border-radius: 3px; font-size: 11px; }
.tag.admin { background: #fa0; color: #fff; }
.tag.player { background: #3a7; color: #fff; }
.x { background: transparent; border: none; color: #999; cursor: pointer; font-size: 16px; padding: 0 4px; }
form { display: flex; flex-direction: column; gap: 10px; }
input { padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 14px; }
button[type=submit] { padding: 10px; background: #0f3460; color: #fff; border: none; border-radius: 4px;
  font-size: 14px; cursor: pointer; }
button[type=submit]:disabled { background: #999; cursor: not-allowed; }
.err { color: #c33; font-size: 12px; margin: 0; }
.hint-default { margin-top: 20px; padding-top: 12px; border-top: 1px dashed #ddd;
  font-size: 12px; color: #666; }
.hint-default summary { cursor: pointer; color: #888; }
.hint-default p { margin: 6px 0; }
.hint-default code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px;
  font-family: monospace; }
.hint-default .warn { color: #c33; }
</style>
