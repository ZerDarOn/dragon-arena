import { reactive } from 'vue'

export interface Toast {
  id: number
  text: string
  type: 'error' | 'warn' | 'info'
}

const toasts = reactive<Toast[]>([])
let nextId = 1

export function pushToast(text: string, type: Toast['type'] = 'error', durationMs = 4000) {
  const id = nextId++
  toasts.push({ id, text, type })
  setTimeout(() => {
    const idx = toasts.findIndex((t) => t.id === id)
    if (idx !== -1) toasts.splice(idx, 1)
  }, durationMs)
}

export function useToast() {
  return { toasts, pushToast }
}
