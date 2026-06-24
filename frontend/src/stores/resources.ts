import { ref, watch } from 'vue'

// 全局资源池（跨组件共享）
interface MonsterTmpl {
  name: string; hp: number; armor: number
  vision_range: number; darkvision: boolean
}
interface ObjTmpl {
  name: string; kind: 'light' | 'container' | 'decor'; light_radius?: number
}

const LS_MONSTERS = 'da_res_monsters'
const LS_EQUIPS = 'da_res_equips'
const LS_OBJECTS = 'da_res_objects'

function load<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return v ? JSON.parse(v) as T : fallback
  } catch { return fallback }
}

export const monsters = ref<MonsterTmpl[]>(load(LS_MONSTERS, []))
export const equips = ref<string[]>(load(LS_EQUIPS, []))
export const objects = ref<ObjTmpl[]>(load(LS_OBJECTS, []))

watch(monsters, (v) => localStorage.setItem(LS_MONSTERS, JSON.stringify(v)), { deep: true })
watch(equips, (v) => localStorage.setItem(LS_EQUIPS, JSON.stringify(v)), { deep: true })
watch(objects, (v) => localStorage.setItem(LS_OBJECTS, JSON.stringify(v)), { deep: true })
