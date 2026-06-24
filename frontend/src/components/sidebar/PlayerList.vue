<template>
  <div class="player-list">
    <h3>玩家列表</h3>
    <ul>
      <li v-for="p in ranked" :key="p.id" :class="{ self: p.id === selfId, dead: p.token?.is_dead }">
        <div class="row1">
          <span class="nick">{{ p.nickname || p.id }}</span>
          <span class="rank">#{{ p._rank }}</span>
          <span v-if="p.is_host" class="tag host">团主</span>
          <span v-if="!p.is_connected" class="tag off">断线</span>
        </div>
        <div class="row2" v-if="p.token">
          <span class="char">{{ p.token.character_name || p.token.name || p.token.id }}</span>
          <span class="prof" v-if="p.profession">{{ p.profession }}</span>
        </div>
        <div class="stats" v-if="p.token">
          <span class="hp" :class="{ low: p.token.hp < p.token.max_hp / 3 }">HP {{ p.token.hp }}/{{ p.token.max_hp }}</span>
          <span class="ap">AP {{ p.token.ap }}/{{ p.token.max_ap }}</span>
          <span class="gold">{{ p.token.gold }}G</span>
          <span class="score">{{ p.token.score }}分</span>
          <span class="vision" title="视野/觉察/隐匿">视{{ p.token.vision_range }}<span v-if="p.token.darkvision">暗</span> 觉{{ p.token.listen_radius }}/{{ p.token.passive_perception }} 隐{{ p.token.stealth }}</span>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoomStore } from '../../stores/room'
import { useSelfStore } from '../../stores/self'

const room = useRoomStore()
const self = useSelfStore()

interface EnrichedPlayer {
  id: string; nickname: string; is_host: boolean; is_connected: boolean
  character_name: string; profession: string; token: any; _rank: number
}

const ranked = computed<EnrichedPlayer[]>(() => {
  const r = room.room
  if (!r) return []
  const players = Object.values(r.players).map((p: any) => ({
    ...p,
    token: p.token_id ? r.tokens[p.token_id] : null,
  }))
  players.sort((a, b) => (b.token?.score || 0) - (a.token?.score || 0))
  players.forEach((p, i) => { p._rank = i + 1 })
  return players
})

const selfId = computed(() => self.playerId)
</script>

<style scoped>
.player-list { font-size: 12px; }
h3 { margin: 0 0 6px; font-size: 13px; color: #0f3460; border-bottom: 1px solid #eee; padding-bottom: 4px; }
ul { list-style: none; padding: 0; margin: 0; }
li { padding: 6px; border-bottom: 1px dashed #eee; }
li.self { background: #fffbe6; }
li.dead { opacity: 0.5; }
.row1 { display: flex; align-items: center; gap: 4px; margin-bottom: 2px; }
.nick { font-weight: bold; flex: 1; }
.rank { color: #888; font-size: 11px; }
.tag { padding: 1px 4px; border-radius: 2px; font-size: 10px; }
.tag.host { background: #fa0; color: #fff; }
.tag.off { background: #999; color: #fff; }
.row2 { font-size: 11px; color: #666; margin-bottom: 2px; }
.char { color: #0f3460; font-weight: 500; }
.prof::before { content: ' · '; }
.stats { display: flex; gap: 6px; font-size: 11px; }
.hp { color: #3a7; }
.hp.low { color: #c33; font-weight: bold; }
.ap { color: #a70; }
.gold { color: #999; }
.vision { color: #69c; font-size: 10px; margin-left: 4px; }
</style>
