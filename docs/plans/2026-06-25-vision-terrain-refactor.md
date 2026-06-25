# 视野/地形/战争迷雾 — 四层视觉模型重构设计

> 日期: 2026-06-25  
> 状态: 待审核  
> 参考: FVTT Token HUD, WarCraft 3 Fog of War, Age of Empires Shroud+Fog

---

## 1. 命名与概念约定

| 术语 | 英文 | 含义 |
|------|------|------|
| 黑幕 | Shroud | 从未探索过的区域，完全不可见（纯黑） |
| 战争迷雾 / 记忆层 | Fog of War | 探索过但当前不在视野内，保留地形旧快照（灰色调） |
| 环境暗 | Darkness | DM 放置的环境暗区（洞穴/地牢），可调强度 |
| 光源 | Light Source | 道具/法术光源，在暗环境中提供局部可见半径 |
| 黑暗视觉 | Darkvision | 角色天赋，可穿透环境暗 |

---

## 2. 四层视觉模型

```
         ┌──────────────────────────────────────────┐
  L4     │         Shroud / Fog of War              │  策略层
         │  未探索=纯黑  已探索+不可见=灰色快照      │  客户端追踪
         ├──────────────────────────────────────────┤
  L3     │         Darkness + Light                 │  环境层
         │  暗区 (可调强度) × 光源 (局部照亮)       │  服务端权威
         ├──────────────────────────────────────────┤
  L2     │         Terrain (Tile)                   │  物理层
         │  flat/wall/grass/water/high              │  墙壁阻断视线
         │  后期支持图片素材                         │
         ├──────────────────────────────────────────┤
  L1     │         Background Image                  │  美术层
         │  纯装饰性底图                              │
         └──────────────────────────────────────────┘
```

**渲染顺序（从下到上）：**

```
1. L1 底图 (bgImage)
2. L2 地形瓦片 (terrain tiles / 颜色填充)
3. L3 环境暗叠加 (darkness overlay)
4. L3 光源叠加 (light source mask — 减法，擦除暗)
5. L4 战争迷雾叠加 (shroud/fog overlay)
6. Token 层（玩家自己的 token 永远不被暗/雾遮盖）
7. UI 层（选择框、路径、AOE 标记）
```

**关键规则：**

- Token 必须渲染在 **所有视觉层之上**。玩家自己的 token 永不暗化。敌方 token 在不可见格子上直接不渲染。
- 环境暗 ≠ 战争迷雾。暗是"环境特征"（改变地貌可见度），雾是"信息限制"（玩家能不能看到这块区域）。
- 战争迷雾的"记忆"状态是**客户端概念**。服务端只算当前可见格子。客户端自己维护一个 `exploredCells: Set<string>`，凡是被标记过可视的格永久记录。

---

## 3. 视野计算（服务端权威）

### 3.1 计算流程

```
computeVisibleCells(token):
  输入: token (含 position, facing, vision_range, darkvision)
  输出: Set<(x, y)>  当前可见格子

  Step 1 — 扇形裁剪
    以 token 朝向 ±45° 全视野, 侧 ±90° 视野 3 格, 背后盲区
    使用 is_in_sector()

  Step 2 — 射线阻断 (wall blocking)
    对每个候选格做 Bresenham 射线
    如果射线上有 type=wall 的格子 → 阻断, 该格不可见
    (高地形/water 暂不阻断, 留扩展点)

  Step 3 — 光源扩散
    如果格子既不在扇形内也没被射线阻断, 但该格 light_radius > 0
    → 在不超 token.vision_range 的前提下加入可见集

  Step 4 — 环境暗过滤
    如果 token.darkvision = true → 跳过此步
    否则: 对每个候选格, 若 is_dark = true 且不在任何光源半径内 → 移除

  Step 5 — 烟雾阻挡
    is_smoke = true 的格子 → 移除 (烟雾是临时效果, 可叠加)
```

### 3.2 数据流

```
客户端请求                服务端                  state_sync 下发
─────────                ──────                  ──────────────
move / end_turn  →  触发 compute_all()    →  room.visible_cells[player_id] = [[x,y],...]
                                         →  room.detected_tokens[player_id] = {tid: "北",...}
```

**状态同步增加字段：**

```typescript
// types.ts - Room 类型已有，无需改结构
interface Room {
  // 已有 — 直接复用
  visible_cells?: [number, number][]           // 当前可见格子 (服务端算)
  detected_tokens?: Record<string, string>    // 被动觉察 (服务端算)
}
```

**客户端新增探索记忆（Pinia store / 独立 composable）：**

```typescript
// 客户端独立维护，不发给服务端
const exploredCells = ref<Set<string>>(new Set())

// 每次 state_sync 后调用
function updateExplored(visibleCells: Set<string>) {
  for (const key of visibleCells) {
    exploredCells.value.add(key)
  }
}
```

---

## 4. 前端渲染管道重构

### 4.1 GameCanvas 渲染重写

当前 `draw()` 函数 200+ 行，所有逻辑平铺。拆分为独立渲染 Pass：

```typescript
// draw() 调用顺序
function draw() {
  clearCanvas()
  drawLayer1_Background()      // 底图
  drawLayer2_Terrain()         // 地形瓦片
  drawLayer3_Darkness()        // 环境暗叠加
  drawLayer3_LightSources()    // 光源 Mask（globalCompositeOperation: 'destination-out'）
  drawLayer4_FogOfWar()        // 黑幕 + 记忆灰层
  drawTokens()                 // Token 层（在暗/雾之上）
  drawUI()                     // 选择/路径/AOE/状态图标
}
```

### 4.2 各层逻辑

**Layer 4 — Fog of War (战争迷雾)**

```
for each cell (x, y):
  key = `${x},${y}`
  if visibleCells.has(key):
    continue  // 可见 → 不放遮罩
  if exploredCells.has(key):
    // 探索过但不可见 → 灰色半透明遮罩（保留地形可见但暗淡）
    ctx.fillStyle = 'rgba(30, 30, 30, 0.65)'
    ctx.fillRect(x*CELL, y*CELL, CELL, CELL)
  else:
    // 从未探索 → 纯黑
    ctx.fillStyle = '#111'
    ctx.fillRect(x*CELL, y*CELL, CELL, CELL)
```

**Layer 3 — 环境暗**

```
for each cell where terrain.is_dark:
  if isAdmin: skip  // 管理员看全图
  strength = terrain.darkness_strength ?? 0.7  // 默认 0.7，DM 可调
  ctx.fillStyle = `rgba(0, 0, 0, ${strength * 0.8})`
  ctx.fillRect(x*CELL, y*CELL, CELL, CELL)
```

**Layer 3 — 光源**

```
使用 globalCompositeOperation = 'destination-out'
对每个 light_radius > 0 的格子, 画渐变透明圆
效果: 在暗层上"挖洞"，露出下方地形
```

**Token 层**

```
for each token:
  if token is self:
    始终渲染 (无视暗/雾)
  else if token on visible cell:
    正常渲染
  else if token in detected_tokens:
    渲染方位标记 (已有逻辑, 不暴露精确位置)
  else:
    不渲染
```

### 4.3 管理员视觉

- 管理员始终看全图（跳过所有暗/雾遮罩）
- 但保留暗/雾的视觉指示（半透明覆盖而非完全遮挡）

---

## 5. 数据模型重构

### 5.1 CellState 统一模型

**当前问题：** `terrain[y][x].type` 和 `terrain[y][x].is_dark` 分离，导致"画黑暗"只改元数据、不改类型，视觉反馈弱。

**方案：** 不拆散属性，但统一 `update_cell` 消息。

```typescript
// schemas/map.py — TerrainCell 保持现有结构，新增字段
class TerrainCell:
    x: int; y: int
    type: str              # flat|wall|grass|water|high
    height: int = 0
    is_dark: bool = False
    darkness_strength: float = 0.7   # 新增：环境暗强度 0.0-1.0
    light_radius: int = 0
    is_smoke: bool = False
    smoke_ttl: int | None = None
```

### 5.2 统一的消息协议

**当前（两个消息、两个通道）：**
```
set_terrain    { x, y, type }
set_cell_meta  { x, y, is_dark?, light_radius? }
```

**重构后（一个消息）：**
```typescript
// 单格操作
{ type: 'update_cell', payload: { x, y, terrain?, is_dark?, darkness_strength?, light_radius? } }

// 批量操作（画笔拖拽 / 矩形填充）
{ type: 'paint_cells', payload: { cells: [{x, y, ...CellState}] } }
```

`fill_terrain` 和 `set_terrain` 合并为 `paint_cells`，支持批量。

### 5.3 后端 handler 变更

```python
# handler.py
elif t == "paint_cells":
    async with gs.lock:
        for cell in p.get("cells", []):
            x, y = cell["x"], cell["y"]
            if "terrain" in cell:
                gs.map_svc.set_terrain(x, y, cell["terrain"])
            if "is_dark" in cell:
                gs.map_svc.set_dark(x, y, cell["is_dark"])
            if "darkness_strength" in cell:
                gs.map_svc.set_darkness_strength(x, y, cell["darkness_strength"])
            if "light_radius" in cell:
                gs.map_svc.set_light(x, y, cell["light_radius"])
        # ...
    await _broadcast_state(gs, room_id)
```

### 5.4 前端画笔面板重构

```
DMConsole — 地形 Tab:

  [笔刷模式: 涂抹 | 画线 | 矩形 | 填充]

  ── 地貌 ──
  [平地] [墙] [草丛] [水] [高地]
  
  ── 环境 ──
  [黑暗]  强度: [=========] 0.7
  [光源]  半径: [=========] 3
  [清除暗/光]

  ── 批量 ──
  x1[  ] y1[  ] → x2[  ] y2[  ]
  类型: [墙 v]  [填充]
```

---

## 6. 聊天用户名修复

### 6.1 根因

[`MessageBubble.vue`](file:///d:/Code/dragon-arena/frontend/src/components/chat/MessageBubble.vue#L7-L8)

```html
<!-- 当前：直接显示原始 sender_id -->
<span class="sender">{{ msg.sender_id }}</span>
```

`msg.sender_id` 是原始用户 ID（如 `user_abc123`），从未从 `room.players` 解析为 `nickname`。

### 6.2 修复方案

在 `MessageBubble.vue` 中添加 computed 属性：

```typescript
import { useRoomStore } from '../../stores/room'

const room = useRoomStore()

const senderName = computed(() => {
  // 系统消息无 sender_id
  if (props.msg.content_type === 'system') return ''
  // 从 room.players 查找昵称
  const player = room.room?.players?.[props.msg.sender_id]
  return player?.nickname || player?.name || props.msg.sender_id
})
```

模板替换：
```html
<span class="sender">{{ senderName }}</span>
```

---

## 7. 黑暗中的 Token 可见性修复

### 7.1 根因

当前渲染管道中，环境暗的 `mixColor(dark)` 覆盖了整个格子，包括格子上的 token。玩家 token 进入暗区后也被暗化。

### 7.2 修复

将 Token 渲染移到暗/雾遮罩**之后**（即上方）。已在第 4.1 节渲染管道中体现。

---

## 8. 实施阶段

### Phase A — 紧急修复（不涉及架构）
- [ ] A1. 聊天用户名显示修复
- [ ] A2. Token 渲染顺序修正（放在暗/雾之上）
- [ ] A3. 暗区笔刷视觉反馈修正（选"黑暗"画笔时，同时把 terrain type 改为有意义的视觉标记）

### Phase B — 数据层统一（向后兼容）
- [ ] B1. TerrainCell 新增 `darkness_strength` 字段（默认 0.7）
- [ ] B2. 新增 `paint_cells` 消息类型，后端 handler 支持
- [ ] B3. 前端 `paintCell` 重构为使用统一 `paint_cells`
- [ ] B4. 旧 `set_terrain` / `set_cell_meta` 保留但标记 deprecated
- [ ] B5. DMConsole 画笔面板重构（地貌 / 环境分组）

### Phase C — 战争迷雾重构
- [ ] C1. 客户端 `exploredCells` 持久化（localStorage per roomId per playerId）
- [ ] C2. GameCanvas 渲染管道拆分为 4 层
- [ ] C3. Layer 4 战争迷雾渲染（黑幕 + 记忆灰层）
- [ ] C4. Layer 3 环境暗 + 光源可视化
- [ ] C5. Token 不受暗/雾遮盖
- [ ] C6. 管理员视觉保留（半透明指示而非全遮挡）

### Phase D — 精细化
- [ ] D1. 环境暗强度滑块（DM 可调）
- [ ] D2. 光源扩散动画（可选）
- [ ] D3. 地形图片素材支持
- [ ] D4. 视野范围边缘柔化

---

## 9. 架构决策记录

### ADR-1: 探索记忆存客户端
- **决策**: 战争迷雾的"已探索"状态由客户端维护，不发送给服务端
- **理由**: 每个玩家探索状态独立，存服务端会 O(N×M) 膨胀；客户端 localStorage 足够
- **代价**: 清浏览器缓存会丢失探索记忆；多设备不共享
- **回滚**: 若后续需要云同步，加一个 `PUT /rooms/{id}/fog` 端点即可

### ADR-2: Token 在所有视觉层之上
- **决策**: Token 渲染在暗/雾遮罩之后，玩家自己的 token 永不暗化
- **理由**: 玩家必须始终能看到自己，这是可用性底线
- **代价**: 可能暴露"暗区里藏了个火把"的视觉不一致（暂可接受）

### ADR-3: 统一 `paint_cells` 替代双通道
- **决策**: 用单一 `paint_cells` 消息替代 `set_terrain` + `set_cell_meta`
- **理由**: 减少前端状态管理复杂度，避免"画黑暗只改元数据不改变类型"的 Bug
- **代价**: 需要重构后端 handler 和前端 paintCell；保留旧消息向后兼容

---

## 10. 风险与注意事项

| 风险 | 缓解 |
|------|------|
| 渲染管道重写导致现有功能回退 | 保留旧 `draw()` 直到新管道测试通过 |
| exploreCells localStorage 膨胀 | 用 BitSet 或 Run-length encoding 压缩 |
| 视野计算增加服务端开销 | 仅在 move/end_turn 时触发，缓存结果 |
| 4 层渲染影响帧率 | 使用离屏 canvas 缓存静态层，仅在变更时重绘 |
