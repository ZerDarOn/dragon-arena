import { useAuthStore } from '../stores/auth'
import type { Item, ItemCreate, ItemUpdate } from './types'

const API = `http://${window.location.hostname}:8000`

function authHeaders(): Record<string, string> {
  const auth = useAuthStore()
  return { 'Content-Type': 'application/json', ...auth.authHeader() }
}

export async function listItems(category?: string): Promise<Item[]> {
  const url = new URL(`${API}/api/items`)
  if (category) url.searchParams.set('category', category)
  const r = await fetch(url.toString(), { headers: authHeaders() })
  if (!r.ok) throw new Error('获取道具库失败')
  return r.json()
}

export async function createItem(data: ItemCreate): Promise<Item> {
  const r = await fetch(`${API}/api/items`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error('创建道具失败')
  return r.json()
}

export async function updateItem(id: string, data: ItemUpdate): Promise<Item> {
  const r = await fetch(`${API}/api/items/${id}`, {
    method: 'PUT',
    headers: authHeaders(),
    body: JSON.stringify(data),
  })
  if (!r.ok) throw new Error('更新道具失败')
  return r.json()
}

export async function deleteItem(id: string): Promise<void> {
  const r = await fetch(`${API}/api/items/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  if (!r.ok) throw new Error('删除道具失败')
}
