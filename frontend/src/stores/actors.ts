// frontend/src/stores/actors.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Actor, ActorCreate, ActorUpdate } from '../api/types'
import * as actorApi from '../api/actors'

export const useActorStore = defineStore('actors', () => {
  const actors = ref<Actor[]>([])
  const loaded = ref(false)

  const players = computed(() => actors.value.filter(a => a.type === 'player'))
  const npcs = computed(() => actors.value.filter(a => a.type === 'npc'))
  const monsters = computed(() => actors.value.filter(a => a.type === 'monster'))

  async function load(force = false) {
    if (loaded.value && !force) return
    actors.value = await actorApi.listActors()
    loaded.value = true
  }

  async function create(data: ActorCreate) {
    const actor = await actorApi.createActor(data)
    actors.value.unshift(actor)
    return actor
  }

  async function update(id: string, data: ActorUpdate) {
    const actor = await actorApi.updateActor(id, data)
    const idx = actors.value.findIndex(a => a.id === id)
    if (idx >= 0) actors.value[idx] = actor
    return actor
  }

  async function remove(id: string) {
    await actorApi.deleteActor(id)
    actors.value = actors.value.filter(a => a.id !== id)
  }

  function getById(id: string): Actor | undefined {
    return actors.value.find(a => a.id === id)
  }

  return { actors, players, npcs, monsters, load, create, update, remove, getById }
})
