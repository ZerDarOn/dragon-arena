import { useAuthStore } from '../stores/auth'
import type { LoginResponse, UserPublic, CharacterSheet, LibraryEntry, RollTable, DrawResult } from './types'

// 跟 api/ws.ts 保持一致：跟着当前访问的 host 走，而不是硬编码 localhost。
// 否则局域网内其他设备访问前端时，WS 能连上但所有 REST 请求都会打到它们自己的本机，永远连不上。
const API = `http://${window.location.hostname}:8000`

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

/**
 * 上传头像，返回可直接用的绝对 URL。
 * 注意：multipart 不能带 Content-Type（让浏览器自动生成 boundary），所以只取 Authorization，
 * 不用 authHeaders()。此前这段逻辑在 ResourceManager / MiniResPanel 里各复制了一份并硬编码了 URL。
 */
export async function listLibrary(category?: string): Promise<LibraryEntry[]> {
  const q = category ? `?category=${encodeURIComponent(category)}` : ''
  const r = await fetch(`${API}/api/library${q}`, { headers: authHeaders() })
  if (!r.ok) throw new Error('加载内容库失败')
  return r.json()
}

/** 导入内容库（管理员）。entries 为 LibraryEntry 数组（与导出格式一致，id 可省略）。 */
export async function importLibrary(entries: any[], mode: 'upsert' | 'replace' = 'upsert'): Promise<any> {
  const r = await fetch(`${API}/api/library/import`, {
    method: 'POST', headers: authHeaders(),
    body: JSON.stringify({ entries, mode }),
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || '导入失败')
  }
  return r.json()
}

// ---- 抽取表 ----
export async function listRollTables(): Promise<RollTable[]> {
  const r = await fetch(`${API}/api/rolltables`, { headers: authHeaders() })
  if (!r.ok) throw new Error('加载抽取表失败')
  return r.json()
}
export async function createRollTable(body: Partial<RollTable>): Promise<RollTable> {
  const r = await fetch(`${API}/api/rolltables`, { method: 'POST', headers: authHeaders(), body: JSON.stringify(body) })
  if (!r.ok) throw new Error('创建抽取表失败')
  return r.json()
}
export async function updateRollTable(id: string, body: Partial<RollTable>): Promise<RollTable> {
  const r = await fetch(`${API}/api/rolltables/${id}`, { method: 'PUT', headers: authHeaders(), body: JSON.stringify(body) })
  if (!r.ok) throw new Error('更新抽取表失败')
  return r.json()
}
export async function deleteRollTable(id: string): Promise<void> {
  const r = await fetch(`${API}/api/rolltables/${id}`, { method: 'DELETE', headers: authHeaders() })
  if (!r.ok) throw new Error('删除抽取表失败')
}
export async function drawRollTable(id: string): Promise<DrawResult> {
  const r = await fetch(`${API}/api/rolltables/${id}/draw`, { method: 'POST', headers: authHeaders() })
  if (!r.ok) throw new Error('抽取失败')
  return r.json()
}

export async function uploadAvatar(file: File): Promise<string> {
  const auth = useAuthStore()
  const form = new FormData()
  form.append('file', file)
  const r = await fetch(`${API}/api/upload/avatar`, {
    method: 'POST', headers: { ...auth.authHeader() }, body: form,
  })
  if (!r.ok) throw new Error('头像上传失败')
  const data = await r.json()
  return `${API}${data.url}`
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
