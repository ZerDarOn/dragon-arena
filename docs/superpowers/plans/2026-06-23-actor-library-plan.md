# Actor Library + Drawing Interaction Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an FVTT-style Actor library where DMs can create/manage character sheets and drag them onto the map to spawn Tokens. Also fix drawing interaction so left-click paints terrain when brush is active, right-click pans.

**Architecture:** 
- Backend: New `Actor` SQLite table + Pydantic schemas + CRUD API + WS spawn_token handler
- Frontend: ResourceManager expanded with Actor CRUD (create/edit/duplicate/delete) + drag-to-canvas spawn
- GameCanvas: Remove paint-mode button, left-click paints when terrainBrush is set, right-click always pans
- Token schema gains `actor_id` field linking back to Actor

**Tech Stack:** FastAPI + SQLite + SQLAlchemy, Vue 3 + Vite + TypeScript + Pinia

---

## File Structure

### Backend (new + modified)

| File | Responsibility |
|------|---------------|
| `backend/app/models/actor.py` | SQLAlchemy Actor model (new table) |
| `backend/app/schemas/actor.py` | Pydantic ActorCreate, ActorUpdate, ActorOut schemas |
| `backend/app/crud/actor.py` | Actor CRUD operations |
| `backend/app/api/actors.py` | REST endpoints: GET/POST/PUT/DELETE /api/actors |
| `backend/app/ws/handler.py` | Add `spawn_token` WS message handler |
| `backend/app/schemas/room.py` | Token schema: add `actor_id?: string` |
| `backend/app/main.py` | Register actors router |

### Frontend (new + modified)

| File | Responsibility |
|------|---------------|
| `frontend/src/api/actors.ts` | Actor API client (REST) |
| `frontend/src/api/types.ts` | Add `Actor`, `ActorCreate`, `ActorUpdate` interfaces |
| `frontend/src/stores/actors.ts` | Pinia store for Actor library (localStorage + API sync) |
| `frontend/src/components/admin/ResourceManager.vue` | Add "角色卡" tab with Actor CRUD + drag-to-spawn |
| `frontend/src/components/board/GameCanvas.vue` | Remove paint-mode button; left-click paints, right-click pans |
| `frontend/src/components/layout/DMConsole.vue` | Remove "单位" tab (replaced by Actor library) |
| `frontend/src/views/MainView.vue` | Wire Actor store, handle spawn-token from canvas drop |

---

## Task 1: Backend Actor Model & Schema

**Files:**
- Create: `backend/app/models/actor.py`
- Create: `backend/app/schemas/actor.py`
- Create: `backend/app/crud/actor.py`
- Modify: `backend/app/database.py` (add Actor to create_tables)

- [ ] **Step 1: Create Actor SQLAlchemy model**

```python
# backend/app/models/actor.py
from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.database import Base

class Actor(Base):
    __tablename__ = "actors"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, default="npc")  # player, npc, monster
    avatar_url = Column(String, nullable=True)
    hp = Column(Integer, default=100)
    max_hp = Column(Integer, default=100)
    armor = Column(Integer, default=5)
    ap = Column(Integer, default=2)
    max_ap = Column(Integer, default=2)
    vision_range = Column(Integer, default=8)
    darkvision = Column(Integer, default=0)
    listen_radius = Column(Integer, default=6)
    passive_perception = Column(Integer, default=10)
    stealth = Column(Integer, default=0)
    # Equipment / skill / backpack stored as JSON strings
    equipment_slots = Column(String, default="[]")  # JSON array of 6 item IDs
    skill_slots = Column(String, default="[]")      # JSON array of 2 skill IDs
    backpack = Column(String, default="[]")         # JSON array of item IDs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

- [ ] **Step 2: Create Pydantic schemas**

```python
# backend/app/schemas/actor.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class ActorBase(BaseModel):
    name: str
    type: str = "npc"  # player, npc, monster
    avatar_url: Optional[str] = None
    hp: int = 100
    max_hp: int = 100
    armor: int = 5
    ap: int = 2
    max_ap: int = 2
    vision_range: int = 8
    darkvision: int = 0
    listen_radius: int = 6
    passive_perception: int = 10
    stealth: int = 0
    equipment_slots: List[str] = Field(default_factory=lambda: [""] * 6)
    skill_slots: List[str] = Field(default_factory=lambda: [""] * 2)
    backpack: List[str] = Field(default_factory=list)

class ActorCreate(ActorBase):
    pass

class ActorUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    avatar_url: Optional[str] = None
    hp: Optional[int] = None
    max_hp: Optional[int] = None
    armor: Optional[int] = None
    ap: Optional[int] = None
    max_ap: Optional[int] = None
    vision_range: Optional[int] = None
    darkvision: Optional[int] = None
    listen_radius: Optional[int] = None
    passive_perception: Optional[int] = None
    stealth: Optional[int] = None
    equipment_slots: Optional[List[str]] = None
    skill_slots: Optional[List[str]] = None
    backpack: Optional[List[str]] = None

class ActorOut(ActorBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True
```

- [ ] **Step 3: Create CRUD operations**

```python
# backend/app/crud/actor.py
import uuid
from sqlalchemy.orm import Session
from app.models.actor import Actor
from app.schemas.actor import ActorCreate, ActorUpdate

def create_actor(db: Session, data: ActorCreate) -> Actor:
    actor = Actor(id=str(uuid.uuid4())[:8], **data.model_dump())
    db.add(actor)
    db.commit()
    db.refresh(actor)
    return actor

def get_actor(db: Session, actor_id: str) -> Actor | None:
    return db.query(Actor).filter(Actor.id == actor_id).first()

def list_actors(db: Session, type: str | None = None) -> list[Actor]:
    q = db.query(Actor)
    if type:
        q = q.filter(Actor.type == type)
    return q.order_by(Actor.created_at.desc()).all()

def update_actor(db: Session, actor_id: str, data: ActorUpdate) -> Actor | None:
    actor = get_actor(db, actor_id)
    if not actor:
        return None
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(actor, k, v)
    db.commit()
    db.refresh(actor)
    return actor

def delete_actor(db: Session, actor_id: str) -> bool:
    actor = get_actor(db, actor_id)
    if not actor:
        return False
    db.delete(actor)
    db.commit()
    return True
```

- [ ] **Step 4: Register Actor table in database init**

```python
# backend/app/database.py
# In create_tables(), ensure Actor is imported so it gets created
from app.models import actor  # noqa: F401
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/actor.py backend/app/schemas/actor.py backend/app/crud/actor.py backend/app/database.py
git commit -m "feat: add Actor model, schema, and CRUD"
```

---

## Task 2: Backend Actor REST API

**Files:**
- Create: `backend/app/api/actors.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create REST endpoints**

```python
# backend/app/api/actors.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.actor import ActorCreate, ActorUpdate, ActorOut
from app.crud import actor as actor_crud
from app.deps import require_admin

router = APIRouter(prefix="/api/actors", tags=["actors"])

@router.get("", response_model=list[ActorOut])
def list_actors(type: str | None = None, db: Session = Depends(get_db), _=Depends(require_admin)):
    return actor_crud.list_actors(db, type=type)

@router.post("", response_model=ActorOut)
def create_actor(data: ActorCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    return actor_crud.create_actor(db, data)

@router.put("/{actor_id}", response_model=ActorOut)
def update_actor(actor_id: str, data: ActorUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    actor = actor_crud.update_actor(db, actor_id, data)
    if not actor:
        raise HTTPException(404, "Actor not found")
    return actor

@router.delete("/{actor_id}")
def delete_actor(actor_id: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    ok = actor_crud.delete_actor(db, actor_id)
    if not ok:
        raise HTTPException(404, "Actor not found")
    return {"ok": True}
```

- [ ] **Step 2: Register router in main.py**

```python
# backend/app/main.py
from app.api import actors
# ... inside app creation ...
app.include_router(actors.router)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/actors.py backend/app/main.py
git commit -m "feat: add Actor REST API endpoints"
```

---

## Task 3: Backend Token Schema + WS Spawn Handler

**Files:**
- Modify: `backend/app/schemas/room.py`
- Modify: `backend/app/ws/handler.py`

- [ ] **Step 1: Add actor_id to Token schema**

```python
# backend/app/schemas/room.py - Token class
class Token(BaseModel):
    id: str
    type: str  # player, monster, summon, corpse, drop
    owner_id: Optional[str] = None
    actor_id: Optional[str] = None  # NEW: links to Actor library
    # ... rest unchanged
```

- [ ] **Step 2: Add spawn_token WS handler**

In `backend/app/ws/handler.py`, add to `handle_ws_connection` message dispatch:

```python
elif msg_type == "spawn_token":
    payload = data.get("payload", {})
    actor_id = payload.get("actor_id")
    x = payload.get("x", 0)
    y = payload.get("y", 0)
    
    # Load actor from DB
    from app.crud import actor as actor_crud
    actor = actor_crud.get_actor(next(get_db()), actor_id)
    if not actor:
        await websocket.send_json({"type": "error", "payload": {"message": "Actor not found"}})
        continue
    
    # Create token from actor template
    token_id = str(uuid.uuid4())[:8]
    token = Token(
        id=token_id,
        type=actor.type,
        owner_id=payload.get("owner_id"),
        actor_id=actor.id,
        name=actor.name,
        avatar_url=actor.avatar_url,
        position=Position(x=x, y=y),
        hp=actor.hp,
        max_hp=actor.max_hp,
        armor=actor.armor,
        ap=actor.ap,
        max_ap=actor.max_ap,
        vision_range=actor.vision_range,
        darkvision=actor.darkvision,
        listen_radius=actor.listen_radius,
        passive_perception=actor.passive_perception,
        stealth=actor.stealth,
        equipment_slots=json.loads(actor.equipment_slots) if isinstance(actor.equipment_slots, str) else actor.equipment_slots,
        skill_slots=json.loads(actor.skill_slots) if isinstance(actor.skill_slots, str) else actor.skill_slots,
        backpack=json.loads(actor.backpack) if isinstance(actor.backpack, str) else actor.backpack,
        states=[],
        is_dead=False,
        is_hidden=False,
        facing=0,
        scale=1.0,
    )
    gs.room.tokens[token_id] = token
    gs.room.turn_order.append(token_id)
    _log_event(gs, player_id, "spawn_token", target=token_id, params={"actor_id": actor_id, "x": x, "y": y})
    await _broadcast_state(gs, room_id)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/room.py backend/app/ws/handler.py
git commit -m "feat: add actor_id to Token and spawn_token WS handler"
```

---

## Task 4: Frontend Actor Types + API Client

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/api/actors.ts`

- [ ] **Step 1: Add Actor interfaces to types.ts**

```typescript
// frontend/src/api/types.ts

export interface Actor {
  id: string
  name: string
  type: 'player' | 'npc' | 'monster'
  avatar_url?: string
  hp: number
  max_hp: number
  armor: number
  ap: number
  max_ap: number
  vision_range: number
  darkvision: number
  listen_radius: number
  passive_perception: number
  stealth: number
  equipment_slots: string[]
  skill_slots: string[]
  backpack: string[]
  created_at: string
  updated_at?: string
}

export interface ActorCreate {
  name: string
  type?: 'player' | 'npc' | 'monster'
  avatar_url?: string
  hp?: number
  max_hp?: number
  armor?: number
  ap?: number
  max_ap?: number
  vision_range?: number
  darkvision?: number
  listen_radius?: number
  passive_perception?: number
  stealth?: number
  equipment_slots?: string[]
  skill_slots?: string[]
  backpack?: string[]
}

export interface ActorUpdate {
  name?: string
  type?: 'player' | 'npc' | 'monster'
  avatar_url?: string
  hp?: number
  max_hp?: number
  armor?: number
  ap?: number
  max_ap?: number
  vision_range?: number
  darkvision?: number
  listen_radius?: number
  passive_perception?: number
  stealth?: number
  equipment_slots?: string[]
  skill_slots?: string[]
  backpack?: string[]
}
```

- [ ] **Step 2: Create Actor API client**

```typescript
// frontend/src/api/actors.ts
import axios from 'axios'
import type { Actor, ActorCreate, ActorUpdate } from './types'

const API = axios.create({ baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8000' })

export async function listActors(type?: string): Promise<Actor[]> {
  const { data } = await API.get('/api/actors', { params: { type }, headers: authHeaders() })
  return data
}

export async function createActor(data: ActorCreate): Promise<Actor> {
  const res = await API.post('/api/actors', data, { headers: authHeaders() })
  return res.data
}

export async function updateActor(id: string, data: ActorUpdate): Promise<Actor> {
  const res = await API.put(`/api/actors/${id}`, data, { headers: authHeaders() })
  return res.data
}

export async function deleteActor(id: string): Promise<void> {
  await API.delete(`/api/actors/${id}`, { headers: authHeaders() })
}

function authHeaders() {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/actors.ts
git commit -m "feat: add Actor types and API client"
```

---

## Task 5: Frontend Actor Pinia Store

**Files:**
- Create: `frontend/src/stores/actors.ts`

- [ ] **Step 1: Create Pinia store**

```typescript
// frontend/src/stores/actors.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Actor, ActorCreate, ActorUpdate } from '@/api/types'
import * as actorApi from '@/api/actors'

export const useActorStore = defineStore('actors', () => {
  const actors = ref<Actor[]>([])
  const loaded = ref(false)

  const players = computed(() => actors.value.filter(a => a.type === 'player'))
  const npcs = computed(() => actors.value.filter(a => a.type === 'npc'))
  const monsters = computed(() => actors.value.filter(a => a.type === 'monster'))

  async function load() {
    if (loaded.value) return
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/stores/actors.ts
git commit -m "feat: add Actor Pinia store"
```

---

## Task 6: ResourceManager Actor Tab + Drag-to-Spawn

**Files:**
- Modify: `frontend/src/components/admin/ResourceManager.vue`

- [ ] **Step 1: Add "角色卡" tab to ResourceManager**

Replace the existing 4-tab structure with 5 tabs: 'monsters', 'equips', 'items', 'actors', 'objects'. The 'actors' tab is new.

```vue
<!-- In ResourceManager.vue tabs -->
<button :class="{ active: activeTab === 'actors' }" @click="activeTab = 'actors'">
  角色卡
</button>
```

- [ ] **Step 2: Add Actor list + CRUD UI in actors tab**

```vue
<div v-if="activeTab === 'actors'" class="tab-panel">
  <div class="toolbar">
    <button @click="showActorForm = true">+ 新建角色</button>
    <input v-model="actorFilter" placeholder="搜索角色..." />
  </div>
  
  <div class="actor-list">
    <div v-for="actor in filteredActors" :key="actor.id" 
         class="actor-card" draggable="true"
         @dragstart="onActorDragStart($event, actor)"
         @click="selectActor(actor)">
      <img v-if="actor.avatar_url" :src="actor.avatar_url" class="avatar" />
      <div class="info">
        <div class="name">{{ actor.name }}</div>
        <div class="meta">{{ typeLabel(actor.type) }} | HP {{ actor.hp }}/{{ actor.max_hp }} | 甲 {{ actor.armor }}</div>
      </div>
      <div class="actions">
        <button @click.stop="editActor(actor)">编辑</button>
        <button @click.stop="duplicateActor(actor)">复制</button>
        <button @click.stop="deleteActor(actor.id)">删除</button>
      </div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add Actor form modal (create/edit)**

```vue
<div v-if="showActorForm" class="modal">
  <div class="modal-content">
    <h3>{{ editingActor ? '编辑角色' : '新建角色' }}</h3>
    <input v-model="actorForm.name" placeholder="名称" />
    <select v-model="actorForm.type">
      <option value="player">玩家</option>
      <option value="npc">NPC</option>
      <option value="monster">怪物</option>
    </select>
    <input v-model="actorForm.avatar_url" placeholder="头像URL" />
    <div class="row">
      <label>HP <input v-model.number="actorForm.hp" type="number" /></label>
      <label>最大HP <input v-model.number="actorForm.max_hp" type="number" /></label>
      <label>护甲 <input v-model.number="actorForm.armor" type="number" /></label>
    </div>
    <div class="row">
      <label>AP <input v-model.number="actorForm.ap" type="number" /></label>
      <label>视野 <input v-model.number="actorForm.vision_range" type="number" /></label>
      <label>暗视 <input v-model.number="actorForm.darkvision" type="number" /></label>
    </div>
    <div class="row">
      <label>听觉 <input v-model.number="actorForm.listen_radius" type="number" /></label>
      <label>被动觉察 <input v-model.number="actorForm.passive_perception" type="number" /></label>
      <label>潜行 <input v-model.number="actorForm.stealth" type="number" /></label>
    </div>
    <div class="actions">
      <button @click="saveActor">保存</button>
      <button @click="showActorForm = false">取消</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Add drag-to-spawn logic**

```typescript
// In ResourceManager.vue script
function onActorDragStart(e: DragEvent, actor: Actor) {
  e.dataTransfer?.setData('application/json', JSON.stringify({
    kind: 'actor',
    actor_id: actor.id,
    name: actor.name,
  }))
}

async function saveActor() {
  if (editingActor.value) {
    await actorStore.update(editingActor.value.id, actorForm.value)
  } else {
    await actorStore.create(actorForm.value)
  }
  showActorForm.value = false
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/admin/ResourceManager.vue
git commit -m "feat: ResourceManager Actor tab with CRUD and drag-to-spawn"
```

---

## Task 7: GameCanvas Drop-to-Spawn + Drawing Interaction Fix

**Files:**
- Modify: `frontend/src/components/board/GameCanvas.vue`

- [ ] **Step 1: Add drop handler for Actor spawn**

```typescript
// In GameCanvas.vue setup
function onDrop(e: DragEvent) {
  e.preventDefault()
  const raw = e.dataTransfer?.getData('application/json')
  if (!raw) return
  const data = JSON.parse(raw)
  if (data.kind === 'actor') {
    const rect = canvasRef.value!.getBoundingClientRect()
    const wx = (e.clientX - rect.left - pan.value.x) / zoom.value
    const wy = (e.clientY - rect.top - pan.value.y) / zoom.value
    const x = Math.floor(wx / CELL)
    const y = Math.floor(wy / CELL)
    emit('spawn-actor', { actor_id: data.actor_id, x, y })
  }
}

// Add to canvas element: @drop="onDrop" @dragover.prevent
```

- [ ] **Step 2: Remove paint-mode button, fix interaction**

Remove the "绘图" button from `.vp-hud`. Change `onDown` logic:

```typescript
function onDown(e: MouseEvent) {
  const [x, y] = getCell(e)

  // Right-click or middle-click always pans
  if (e.button === 1 || e.button === 2) { e.preventDefault(); startPan(e); return }
  if (e.button !== 0) return

  // Left-click + terrainBrush active → paint (highest priority)
  if (props.terrainBrush) {
    terrainPaintStart.value = [x, y]
    terrainPaintQueue.value = []
    if (terrainPaintMode.value === 'single') {
      paintCell(x, y)
    }
    return
  }
  // ... rest unchanged
}
```

Also remove `paintMode` ref, `togglePaintMode`, and `paintModeLabel` from GameCanvas. The terrain brush is active whenever `props.terrainBrush` is set.

- [ ] **Step 3: Update emit definitions**

```typescript
const emit = defineEmits<{
  // ... existing emits ...
  (e: 'spawn-actor', payload: { actor_id: string; x: number; y: number }): void
}>()
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/board/GameCanvas.vue
git commit -m "feat: canvas drop-to-spawn, remove paint-mode button, left-click paint right-click pan"
```

---

## Task 8: MainView Wire-up + DMConsole Cleanup

**Files:**
- Modify: `frontend/src/views/MainView.vue`
- Modify: `frontend/src/components/layout/DMConsole.vue`

- [ ] **Step 1: Wire Actor store in MainView**

```typescript
// In MainView.vue script setup
import { useActorStore } from '@/stores/actors'
const actorStore = useActorStore()
onMounted(() => {
  // ... existing init ...
  actorStore.load()
})

// Handle spawn-actor from canvas
function onSpawnActor(payload: { actor_id: string; x: number; y: number }) {
  ws?.send(JSON.stringify({
    type: 'spawn_token',
    payload: { actor_id: payload.actor_id, x: payload.x, y: payload.y }
  }))
}
```

- [ ] **Step 2: Remove "单位" tab from DMConsole**

Delete the `place` tab and all related code (unit placement UI, pendingUnit, etc.). The Actor library in ResourceManager replaces this.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/MainView.vue frontend/src/components/layout/DMConsole.vue
git commit -m "feat: wire Actor spawn in MainView, remove DMConsole unit tab"
```

---

## Task 9: Integration Test

- [ ] **Step 1: Start backend and frontend**

```bash
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```

- [ ] **Step 2: Test flow**

1. Open ResourceManager → 角色卡 tab
2. Click "+ 新建角色" → fill form → save
3. Drag actor card onto canvas → token should spawn at drop location
4. Verify token has correct HP/Armor/Vision from Actor template
5. Select terrain brush in DMConsole → left-click on canvas → paints terrain
6. Right-click drag → pans map
7. Select "选择" tool → left-click on token → selects token

- [ ] **Step 3: Fix any issues found**

- [ ] **Step 4: Final commit**

```bash
git commit -m "feat: Actor library and drawing interaction refactor complete"
```

---

## Spec Coverage Check

| Spec Requirement | Task |
|-----------------|------|
| Actor model in backend | Task 1 |
| Actor REST API | Task 2 |
| Token links to Actor | Task 3 |
| Actor types + API client | Task 4 |
| Actor Pinia store | Task 5 |
| ResourceManager Actor CRUD | Task 6 |
| Drag actor to spawn token | Task 6, 7 |
| Left-click paint / right-click pan | Task 7 |
| Remove paint-mode button | Task 7 |
| Remove DMConsole unit tab | Task 8 |
| MainView wire-up | Task 8 |

All requirements covered. No placeholders in plan.
