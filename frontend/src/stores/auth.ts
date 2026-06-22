import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserPublic, LoginResponse } from '../api/types'

const TOKEN_KEY = 'dragon_arena_token'
const USER_KEY = 'dragon_arena_user'
const HISTORY_KEY = 'dragon_arena_login_history'

export interface LoginHistoryEntry {
  nickname: string
  role: 'admin' | 'player'
  lastLoginAt: number
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_KEY))
  const user = ref<UserPublic | null>(
    (() => {
      try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') } catch { return null }
    })()
  )
  const history = ref<LoginHistoryEntry[]>(loadHistory())

  const isLoggedIn = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => !!user.value?.is_admin)

  function loadHistory(): LoginHistoryEntry[] {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { return [] }
  }

  function persistHistory() {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
  }

  function addHistory(nickname: string, isAdminFlag: boolean) {
    const role: 'admin' | 'player' = isAdminFlag ? 'admin' : 'player'
    const existing = history.value.find((h) => h.nickname === nickname)
    if (existing) {
      existing.role = role
      existing.lastLoginAt = Date.now()
    } else {
      history.value.push({ nickname, role, lastLoginAt: Date.now() })
    }
    persistHistory()
  }

  function removeHistory(nickname: string) {
    history.value = history.value.filter((h) => h.nickname !== nickname)
    persistHistory()
  }

  function setSession(data: LoginResponse) {
    token.value = data.token
    user.value = data.user
    localStorage.setItem(TOKEN_KEY, data.token)
    localStorage.setItem(USER_KEY, JSON.stringify(data.user))
    addHistory(data.user.nickname, data.user.is_admin)
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }

  /** Authorization header value for fetch calls. */
  function authHeader(): Record<string, string> {
    return token.value ? { Authorization: `Bearer ${token.value}` } : {}
  }

  return {
    token, user, history, isLoggedIn, isAdmin,
    setSession, logout, authHeader,
    addHistory, removeHistory,
  }
})
