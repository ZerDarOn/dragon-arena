import { useAuthStore } from '../stores/auth'
import type { Actor, ActorCreate, ActorUpdate } from './types'

const API = 'http://localhost:8000'

function authHeaders(): Record<string, string> {
  const auth = useAuthStore()
  return { 'Content-Type': 'application/json', ...auth.authHeader() }
}

export async function listActors(type?: string): Promise<Actor[]> {
  const url = new URL(`${API}/api/actors`)
  if (type) url.searchParams.set('type', type)
  const r = await fetch(url.toString(), { headers: authHeaders() })
  if (!r.ok) throw new Error('获取角色模板失败')
  return r.json()
}

export async function createActor(data: ActorCreate): Promise<Actor> {
  const r = await fetch(`${API}/api/actors`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error('创建角色模板失败')
  return r.json()
}

export async function updateActor(id: string, data: ActorUpdate): Promise<Actor> {
  const r = await fetch(`${API}/api/actors/${id}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error('更新角色模板失败')
  return r.json()
}

export async function deleteActor(id: string): Promise<void> {
  const r = await fetch(`${API}/api/actors/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error('删除角色模板失败')
}
