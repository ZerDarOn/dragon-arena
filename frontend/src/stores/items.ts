// frontend/src/stores/items.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Item, ItemCreate, ItemUpdate } from '../api/types'
import * as itemApi from '../api/items'

export const useItemStore = defineStore('items', () => {
  const items = ref<Item[]>([])
  const loaded = ref(false)

  async function load(force = false) {
    if (loaded.value && !force) return
    items.value = await itemApi.listItems()
    loaded.value = true
  }

  async function create(data: ItemCreate) {
    const item = await itemApi.createItem(data)
    items.value.unshift(item)
    return item
  }

  async function update(id: string, data: ItemUpdate) {
    const item = await itemApi.updateItem(id, data)
    const idx = items.value.findIndex(i => i.id === id)
    if (idx >= 0) items.value[idx] = item
    return item
  }

  async function remove(id: string) {
    await itemApi.deleteItem(id)
    items.value = items.value.filter(i => i.id !== id)
  }

  function getByName(name: string): Item | undefined {
    return items.value.find(i => i.name === name)
  }

  return { items, loaded, load, create, update, remove, getByName }
})
