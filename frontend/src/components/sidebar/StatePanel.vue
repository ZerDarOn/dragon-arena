<template>
  <div class="state-panel">
    <h3>状态 <span v-if="token" class="target">→ {{ displayName(token) }}</span></h3>
    <select v-if="!token && isAdmin" v-model="tokenId">
      <option value="">选择目标...</option>
      <option v-for="t in tokens" :key="t.id" :value="t.id">{{ displayName(t) }}</option>
    </select>
    <ul class="states">
      <li v-for="s in states" :key="s.id" :class="stateClass(s.name)">
        <strong>{{ s.name }}</strong>
        <span class="ttl" :class="{ urgent: s.ttl <= 1 }"">{{ s.ttl }}回合</span>
        <span class="intensity" v-if="s.intensity"">强度{{ s.intensity }}</span>
        <span class="desc" v-if="s.description">— {{ s.description }}</span>
      </li>
      <li v-if="!states.length" class="empty">无状态</li>
    </ul>
    <div class="add" v-if="isAdmin || token">
      <input v-model="name" placeholder="状态名（如：中毒）" />
      <input v-model="description" placeholder="描述（可选）" />
      <input v-model.number="ttl" type="number" placeholder="回合" />
      <button @click="add">添加</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoomStore } from '../../stores/room'
import { useAuthStore } from '../../stores/auth'

const props = defineProps<{ token?: any }>()
const room = useRoomStore()
const auth = useAuthStore()
const isAdmin = computed(() => auth.isAdmin)
const tokens = computed(() => Object.values(room.room?.tokens ?? {}))
const tokenId = ref(props.token?.id ?? '')
const name = ref(''); const description = ref(''); const ttl = ref(1)

const targetId = computed(() => props.token?.id ?? tokenId.value)
const states = computed(() => room.room?.tokens[targetId.value]?.states ?? [])

function displayName(t: any): string {
  return t?.character_name || t?.type || t?.id || '?'
}

function add() {
  if (!targetId.value || !name.value) return
  window.dispatchEvent(new CustomEvent('ws-send', {
    detail: {
      type: 'add_state',
      payload: { token_id: targetId.value, name: name.value, description: description.value, ttl: ttl.value },
    },
  }))
  name.value = ''; description.value = ''; ttl.value = 1
}

function stateClass(name: string) {
  const debuffs = ['中毒', '点燃', '流血', '撕裂', '定身', '沉默', '护甲降低']
  const buffs = ['隐身', '护盾', '加速']
  if (debuffs.includes(name)) return 'debuff'
  if (buffs.includes(name)) return 'buff'
  return ''
}
</script>

<style scoped>
.state-panel { font-size: 12px; }
h3 { margin: 0 0 6px; font-size: 13px; color: #0f3460; border-bottom: 1px solid #eee; padding-bottom: 4px; }
.target { color: #fa0; font-size: 11px; }
.states { list-style: none; padding: 0; margin: 0 0 8px; }
.states li.debuff { background: #fff0f0; }
.states li.buff { background: #f0fff0; }
.ttl.urgent { color: #c33; font-weight: bold; }
.intensity { color: #a70; margin-left: 4px; font-size: 11px; }
.states li.empty { color: #999; text-align: center; }
.ttl { color: #c33; margin-left: 6px; font-size: 11px; }
.desc { color: #666; font-size: 11px; }
.add { display: flex; flex-direction: column; gap: 4px; }
.add input { padding: 4px; font-size: 12px; border: 1px solid #ccc; border-radius: 3px; }
.add button { padding: 4px; background: #0f3460; color: #fff; border: none; border-radius: 3px; cursor: pointer; }
select { padding: 4px; font-size: 12px; border: 1px solid #ccc; border-radius: 3px; margin-bottom: 6px; width: 100%; box-sizing: border-box; }
</style>
