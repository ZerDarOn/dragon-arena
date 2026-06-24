import { useAuthStore } from '../stores/auth'
import type { LoginResponse, UserPublic, CharacterSheet } from './types'

const API = 'http://localhost:8000'

function authHeaders(): Record<string, string> {
  const auth = useAuthStore()
  return { 'Content-Type': 'application/json', ...auth.authHeader() }
}

export async function login(nickname: string, password: string): Promise<LoginResponse> {
  const r = await fetch(`${API}/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nickname, password }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || '登录失败')
  }
  return r.json()
}

export async function fetchMe(): Promise<UserPublic> {
  const r = await fetch(`${API}/auth/me`, { headers: authHeaders() })
  if (!r.ok) throw new Error('token 失效')
  return r.json()
}

export async function adminListUsers(): Promise<UserPublic[]> {
  const r = await fetch(`${API}/admin/users`, { headers: authHeaders() })
  if (!r.ok) throw new Error('无法获取用户列表')
  return r.json()
}

export async function adminCreateUser(nickname: string, password: string, isAdmin: boolean): Promise<UserPublic> {
  const r = await fetch(`${API}/admin/users`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ nickname, password, is_admin: isAdmin }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || '创建用户失败')
  }
  return r.json()
}

export async function adminDeleteUser(userId: string): Promise<void> {
  const r = await fetch(`${API}/admin/users/${userId}`, {
    method: 'DELETE', headers: authHeaders(),
  })
  if (!r.ok) throw new Error('删除用户失败')
}

// ---- Characters ----

export async function listMyCharacters(): Promise<CharacterSheet[]> {
  const r = await fetch(`${API}/characters`, { headers: authHeaders() })
  if (!r.ok) throw new Error('获取角色卡失败')
  return r.json()
}

export async function listAllCharacters(): Promise<CharacterSheet[]> {
  const r = await fetch(`${API}/admin/characters`, { headers: authHeaders() })
  if (!r.ok) throw new Error('获取全部角色卡失败')
  return r.json()
}

export async function createCharacter(body: Omit<CharacterSheet, 'id' | 'owner_id' | 'created_at' | 'updated_at'>): Promise<CharacterSheet> {
  const r = await fetch(`${API}/characters`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error('创建角色卡失败')
  return r.json()
}

export async function updateCharacter(id: string, body: Omit<CharacterSheet, 'id' | 'owner_id' | 'created_at' | 'updated_at'>): Promise<CharacterSheet> {
  const r = await fetch(`${API}/characters/${id}`, {
    method: 'PUT', headers: authHeaders(),
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error('更新角色卡失败')
  return r.json()
}

export async function deleteCharacter(id: string): Promise<void> {
  const r = await fetch(`${API}/characters/${id}`, {
    method: 'DELETE', headers: authHeaders(),
  })
  if (!r.ok) throw new Error('删除角色卡失败')
}

// ---- Rooms ----

export async function createRoom(name: string) {
  const r = await fetch(`${API}/rooms`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ name }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || '创建战役失败')
  }
  return r.json()
}

export async function listRooms() {
  const r = await fetch(`${API}/rooms`, { headers: authHeaders() })
  if (!r.ok) throw new Error('获取房间列表失败')
  return r.json()
}

export async function getRoom(roomId: string) {
  const r = await fetch(`${API}/rooms/${roomId}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('房间不存在')
  return r.json()
}

export async function updateRoomConfig(roomId: string, body: Record<string, any>) {
  const r = await fetch(`${API}/rooms/${roomId}/config`, {
    method: 'PATCH', headers: authHeaders(),
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error('更新房间配置失败')
  return r.json()
}
