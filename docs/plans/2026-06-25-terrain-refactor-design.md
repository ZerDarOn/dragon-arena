# 地形系统重构设计文档

> 日期: 2026-06-25
> 状态: 设计稿，待确认
> 参考: FVTT Canvas Layers / Walls Layer; Owlbear Rodeo Scene/Map 分离

---

## 1. 问题诊断

### 1.1 当前系统的根本缺陷

所有地形属性耦合在 `TerrainCell.type` 单字段里：

```
type: "flat" | "wall" | "grass" | "water" | "high"
```

**无法表达组合**：
- 草地上的墙？不可能（要么 grass 要么 wall）
- 水中黑暗？不可能（要么 water 要么 dark）
- 烟雾里的墙？不可能

**碰撞逻辑硬编码**：
```python
def is_wall(x, y):
    return self.map.terrain[y][x].type == "wall"  # 只有 wall 阻挡
```
- 水到底挡不挡移动？代码里没判断（目前不挡）
- 烟雾挡视野吗？没有在 is_wall 里体现

### 1.2 FVTT 的做法（核心参考）

FVTT 把这些**全部拆成独立层/对象**：

| 概念 | 层 | 数据 | 碰撞 | 视野 |
|---|---|---|---|---|
| 底图（视觉） | Background Layer | Scene.img | — | — |
| 地面材质 | Tiles (underfoot) | Tile 对象数组 | — | — |
| **墙壁** | **Walls Layer** | **Wall 对象数组** | ✅ | ✅ |
| 光照 | Lighting Layer | Light 对象数组 | — | ✅ |
| 临时效果 | Tiles / Effects | Tile 对象 | 可选 | 可选 |

关键：**FVTT 的墙不是格子属性，而是独立的"墙对象"**，有：
- 坐标（线段端点，不是格子中心）
- 类型（wall/door/ethereal/terrain）
- 朝向（单面墙只挡一侧）
- 开关状态（门）

### 1.3 枭雄的做法（简化参考）

枭雄更轻量：
- 底图就是一切视觉
- 碰撞靠 DM 手动画"不可通行区域"
- 没有结构化的墙对象，靠网格 mask

---

## 2. 重构目标

### 2.1 设计原则

1. **三维度解耦**：地貌（视觉）、碰撞（逻辑）、环境（光照）独立设置
2. **组合友好**：一个格子可以同时是"草地 + 有墙 + 黑暗"
3. **扩展性强**：新地形类型不需要改碰撞/视野逻辑
4. **DM 易用**：画笔面板分组清晰，操作直觉
5. **向后兼容**：旧 `type` 字段平滑迁移

### 2.2 不做什么（边界）

- ❌ 不做 FVTT 的线段墙（坐标是格子中心，不是线段端点）—— 我们的地图是格子制，线段墙过度设计
- ❌ 不做墙朝向（单面墙）—— 当前视野是基于格子的 ray-casting，不需要
- ❌ 不做墙的开关动画—— 门先做逻辑开关，视觉后续补
- ❌ 不做多层层级（overhead/underfoot tiles）—— 当前架构是单层格子

---

## 3. 数据模型

### 3.1 TerrainCell 重构

```python
class TerrainCell(BaseModel):
    x: int
    y: int

    # ─── 维度1: 地貌（纯视觉，影响渲染颜色/纹理） ───
    terrain_type: str = "flat"
    # flat | grass | dirt | stone | sand | water | lava | ice | wood
    # 纯视觉分类，不影响碰撞和视野

    # ─── 维度2: 碰撞/阻挡（逻辑层） ───
    blocks_movement: bool = False
    # true = 不能走过去（墙、深水、岩浆）
    # false = 可以走（平地、草地、浅水）

    blocks_vision: bool = False
    # true = 视野被阻挡（实体墙、烟雾、浓密树丛）
    # false = 可以看过去（玻璃、浅水、栏杆）

    # ⚠️ blocks_movement + blocks_vision 是唯一碰撞真相（见 ADR-1）
    # wall_type 仅是渲染标签，不参与任何碰撞/视野/声音判断

    wall_render: Optional[str] = None
    # 渲染标签（仅影响画法），不参与碰撞判断
    # None = 普通地形渲染
    # "solid" = 实体墙渲染（半格视觉，§8）
    # "door" = 门渲染（带开/关门图标）
    # "glass" = 玻璃/透明材质渲染
    # "water_deep" = 深水渲染（波纹动效）
    # 扩展预留: "lava", "one_way", ...

    door_open: bool = False  # 门的开关状态（渲染+碰撞都看这个）

    # ─── 维度3: 环境（光照系统，保持不变） ───
    is_dark: bool = False
    darkness_strength: float = 0.7
    light_radius: int = 0

    # ─── 辅助属性 ───
    height: int = 0          # 高地（战术优势，不影响碰撞）
    is_smoke: bool = False   # 烟雾（临时效果，blocks_vision 由 is_smoke 派生，见 ADR-4）
    smoke_ttl: Optional[int] = None

    # ─── 废弃字段（迁移期保留，重构后删除） ───
    # type: str = "flat"  → 迁移到 terrain_type + blocks_*
```

> **ADR-1：布尔是唯一碰撞真相**
> - `blocks_movement` + `blocks_vision` 是碰撞的**唯一数据源**
> - `wall_render` 是**纯渲染标签**，碰撞代码永远不读它
> - 预设表（§3.2）只是给 DM 画笔的快捷方式：选预设 = 一次性设好布尔 + 渲染标签
> - **如果出现 wall_render="solid" 但 blocks_movement=false** 的不一致数据，以布尔为准（渲染层容错降级为普通地形画法）
> - 这样避免了"两套模型同时存"的歧义

### 3.2 预设地形表（DM 画笔用）

DM 不需要手动设 3 个字段，系统提供预设：

| 预设名 | terrain_type | blocks_movement | blocks_vision | wall_type | 说明 |
|---|---|---|---|---|---|
| 平地 | flat | false | false | None | 默认 |
| 草地 | grass | false | false | None | 纯视觉 |
| 泥地 | dirt | false | false | None | 纯视觉 |
| 石地 | stone | false | false | None | 纯视觉 |
| 沙地 | sand | false | false | None | 纯视觉 |
| 木板 | wood | false | false | None | 纯视觉 |
| 浅水 | water | false | false | None | 可趟水 |
| 深水 | water | true | false | "movement" | 不能走，能看 |
| 岩浆 | lava | true | false | "movement" | 不能走+伤害 |
| 冰面 | ice | false | false | None | 可走（可能打滑，逻辑后补） |
| **实体墙** | stone | true | true | "solid" | 挡一切 |
| **门** | wood | true | true | "door" | 可开关 |
| **透明墙** | glass | false | true | "vision" | 挡视野不挡移动 |
| **移动墙** | stone | true | false | "movement" | 挡移动不挡视野 |
| 烟雾 | flat | false | true | None | 临时（is_smoke=true） |

### 3.3 DM 画笔面板分组（UX）

```
┌─ 地貌（纯视觉，不挡路） ──┐
│  [平地] [草地] [泥地]      │
│  [石地] [沙地] [木板]      │
│  [浅水] [冰面]             │
└───────────────────────────┘

┌─ 障碍（挡移动/视野） ─────┐
│  [实体墙] [门]             │
│  [透明墙] [移动墙]         │
│  [深水]   [岩浆]           │
└───────────────────────────┘

┌─ 环境 ───────────────────┐
│  [黑暗] [光源] [烟雾]      │
│  [清除环境]               │
└───────────────────────────┘
```

**关键 UX 改进**：
- 画笔分 3 组，DM 一眼就知道选的是"纯视觉"还是"会挡路"
- 鼠标悬停每个画笔显示 tooltip 说明（挡不挡路/视野）
- 选了"门"画笔后，格子上的门有开/关状态指示（DM 可切换）

---

## 4. 碰撞与视野逻辑

### 4.1 is_wall → is_passable / is_vision_blocking

```python
# 替换原来的 is_wall
def is_passable(self, x: int, y: int) -> bool:
    """是否可通行（移动碰撞检测）"""
    if not self._in_bounds(x, y):
        return False  # 地图边界不可走
    cell = self.map.terrain[y][x]
    if cell.blocks_movement:
        if cell.wall_type == "door" and cell.door_open:
            return True  # 门开着可以走
        return False
    return True

def is_vision_blocking(self, x: int, y: int) -> bool:
    """是否阻挡视野（视野计算用）"""
    if not self._in_bounds(x, y):
        return True  # 地图边界挡视野
    cell = self.map.terrain[y][x]
    if cell.blocks_vision:
        if cell.wall_type == "door" and cell.door_open:
            return False  # 门开着不挡视野
        return True
    return False
```

### 4.2 调用方更新

| 位置 | 原代码 | 新代码 |
|---|---|---|
| token_service.move_along_path | `is_wall(step)` | `is_passable(step)` |
| token_service._walkable_cells | `is_wall(x,y)` | `is_passable(x,y)` |
| token_service._edge_cells | `is_wall(x,y)` | `is_passable(x,y)` |
| vision_service（视野计算） | （需确认是否有 is_wall 调用） | `is_vision_blocking(x,y)` |

---

## 5. 迁移策略

### 5.1 数据迁移

旧 `type` 字段 → 新三维字段的映射规则：

| 旧 type | terrain_type | blocks_movement | blocks_vision | wall_type |
|---|---|---|---|---|
| flat | flat | false | false | None |
| grass | grass | false | false | None |
| water | water | false | false | None（旧水不挡移动） |
| wall | stone | true | true | "solid" |
| high | stone | false | false | None（height 字段保留） |

迁移方式：后端 startup 时检测旧格式，自动转换（一次性脚本或懒加载转换）。

### 5.2 paint_cells 协议更新

```
# 旧
{ "type": "set_terrain", "cell": {"x":1,"y":2,"type":"wall"} }

# 新（预设模式，DM 画笔用）
{ "type": "paint_cells", "cells": [{"x":1,"y":2,"preset":"wall"}] }

# 新（精细模式，直接设字段）
{ "type": "paint_cells", "cells": [{"x":1,"y":2,"terrain_type":"stone","blocks_movement":true,"wall_type":"solid"}] }
```

### 5.3 前端渲染更新

`drawLayer2_Terrain` 按 `terrain_type` 决定颜色/纹理：
- 有底图时：只有非 flat 的 terrain_type 或有障碍标记的格子才画覆盖层
- 无底图时：所有格子画纯色（兼容旧体验）

障碍格子的视觉指示：
- solid 墙：不透明深色 + 墙纹理
- door：木色 + 门图标（开/关状态）
- vision 墙：半透明蓝色（表示挡视野不挡移动）
- movement 墙：半透明红色（表示挡移动不挡视野）

---

## 6. 前端类型定义

```typescript
// types.ts
interface TerrainCell {
  x: number; y: number
  terrain_type: string      // flat/grass/dirt/stone/...
  blocks_movement: boolean
  blocks_vision: boolean
  wall_type?: string | null // solid/door/vision/movement
  door_open?: boolean
  is_dark: boolean
  darkness_strength: number
  light_radius: number
  height: number
  is_smoke: boolean
  smoke_ttl?: number | null
  // 迁移期保留
  type?: string
}
```

---

## 7. DM 编辑模式（参考 FVTT/枭雄）

### 7.1 问题

DM 编辑地形时（画墙、设黑暗、对齐底图），需要：
- 看清网格线（底图太亮/太杂时网格被淹没）
- 看清已画的地形标记（墙/障碍的位置）
- 底图不能完全遮盖编辑信息

当前系统没有"编辑模式"，底图 + 地形 + 网格全混在一起，编辑时很难看清。

### 7.2 FVTT/枭雄的做法

**FVTT**：不做底图减淡，而是：
- 每个 layer（墙/光/地形）独立可见性切换
- 激活某 layer 的工具时，该 layer 自动高亮
- 网格有独立的 alpha 控制
- 模块 Dragon Flagon Architect 提供跨层可见（编辑墙时也能看到光源）

**枭雄**：
- 网格独立配置：`gridOpacity`（0-1）、`gridColor`（自动适应底图明暗）、`gridLineType`（实线/虚线）
- 迷雾对 DM 是半透明的（编辑态），点 `Enable Fog Preview` 切到玩家视角（全黑）
- 底图和网格完全分离，网格叠加在底图上

**核心思想**：不是"减淡底图"，而是"增强编辑层可见性"。编辑层（网格、墙壁标记、碰撞区域）始终清晰可见，叠加在底图之上。

### 7.3 我们的方案：DM 视图增强

**不搞全局编辑模式开关**（太重），而是：

1. **网格层独立化**（最重要）
   - 当前网格线和地形格子边框是耦合的（drawLayer2 里 strokeRect）
   - 拆出独立的 `drawGrid(ctx)` 函数，在所有层之上画网格线
   - DM 可调网格透明度/颜色（画笔面板里有滑块）
   - 有底图时网格线加亮（避免被底图淹没）

2. **DM 专属叠加层**
   - DM 看到的画布比玩家多一层 `drawDmOverlay(ctx)`
   - 在这一层画：
     - 障碍标记（墙/门的图标/颜色边框）
     - 碰撞可视化（可选 toggle：红色=不可走，蓝色=挡视野）
     - 门开关状态指示
   - 这一层只在 `isAdmin` 时渲染，玩家永远看不到

3. **底图透明度已有**（bg_opacity 滑块）
   - DM 编辑时可以临时调低底图透明度到 0.2-0.3
   - 这是最简单直接的方案，已有功能，无需新开

4. **网格自动适配底图明暗**（学枭雄）
   - 当有底图时，采样底图平均亮度
   - 亮底图 → 网格线用深色（#333 半透明）
   - 暗底图 → 网格线用浅色（#fff 半透明）
   - 纯前端计算，不需要后端

### 7.4 渲染管道更新

```
当前:
  L1 底图 → L2 地形(含网格) → L3 暗/光 → L4 迷雾 → Token

更新后:
  L1 底图
  → L2 地形地貌（纯视觉，有底图时平地透明）
  → L3 暗/光
  → L4 迷雾
  → L5 网格线（独立层，DM 可调）
  → Token
  → L6 DM 叠加层（障碍标记/碰撞可视化，仅管理员）
  → L7 UI（画笔预览/悬停/拖拽路径）
```

关键改动：
- 网格从 L2 里拆出来成为独立的 L5
- 新增 L6 DM 叠加层
- 网格永远在地形之上（编辑时看得清）

---

## 8. 半格视觉墙（空间优化）

### 8.1 问题

格子制墙占满整个格子，画建筑时墙吃掉太多空间。30x30 地图画房间后可用面积可能只剩 60%。

### 8.2 方案：邻居感知的半格渲染

碰撞逻辑不变（还是整格阻挡），只是**渲染时墙只画半格厚**：

```
判断墙的朝向（根据 4 邻居）:
  - 左右都是墙 → 水平墙（画上半格）
  - 上下都是墙 → 垂直墙（画左半格）
  - 孤立墙 → 全格（默认）
  - 拐角（L 形邻居）→ 画 L 形半格
```

实现：在 `drawLayer2_Terrain` 里，对 `wall_render == "solid"` 的格子，检查邻居后决定画哪个半格。纯渲染层改动，零碰撞逻辑风险。

---

## 9. 实施阶段（更新）

### Phase 1: 后端模型 + 逻辑（🔴 三条验收红线）
- TerrainCell 新增三维字段（terrain_type / blocks_movement / blocks_vision / wall_render / door_open）
- map_service 新增 **三个谓词**：is_passable / is_vision_blocking / is_sound_blocking
- 旧 is_wall 保留为兼容垫片（= is_sound_blocking 语义）
- **8 个调用点逐一替换**（§4.2 清单）
- 快照迁移：`GameMap.model_validator(mode="after")` 懒加载回填（§5.2）
- paint_cells 支持 preset 参数
- 后端测试更新

**Phase 1 验收标准（三条红线，缺一不开 Phase 2）**：
1. ✅ **布尔为唯一碰撞真相**：碰撞/视野/声音代码中无 `wall_render` 读取（grep 验证）
2. ✅ **快照迁移回填通过测试**：造旧 JSON（`{"type":"wall"}`），反序列化后 `blocks_movement==True, blocks_vision==True`
3. ✅ **三个谓词各有测试**：passable/vision/sound 各至少 1 个单元测试覆盖

### Phase 2: 前端渲染 + 画笔 UX
- types.ts 更新
- 网格拆出为独立 drawGrid 层
- drawLayer2_Terrain 按 terrain_type 渲染（有底图时平地透明）
- 半格视觉墙（邻居感知，读 wall_render="solid"）
- DMConsole 画笔面板分 3 组：地貌/障碍/环境

### Phase 3: DM 视图增强
- DM 叠加层（障碍标记/门开关状态）
- 网格透明度/颜色可调
- 底图明暗自适应网格色

### Phase 4: 高级功能
- 门开关交互（DM 点击门切换 door_open）
- 危险地形伤害（岩浆/毒沼 per-turn dot）
- 深水下沉/下潜逻辑
- 地形纹理/图片素材

---

## 10. 设计决策记录

### 10.1 水域（浅水/深水）
- **决策**：都是 `terrain_type="water"`，都**可走**（blocks_movement=false）
- **区分**：深水用 `wall_render="water_deep"`（视觉标记），不加碰撞字段
- **深水逻辑**：可走但可"下潜/下沉"（后续 Phase 4 实现，先做视觉区分）

### 10.2 门（多功能）
- **决策**：`wall_render="door"` + `door_open` 开关状态
- **多功能**：DM 可点击切换开/关，关=挡移动+挡视野，开=都不挡
- **不做钥匙/权限**：门是全局开关，所有玩家看到同样状态

### 10.3 岩浆/毒沼（伤害地形）
- **决策**：`terrain_type="lava"/"poison"` + `blocks_movement=true`
- **伤害**：加 `terrain_dot_damage: int` 字段（每回合伤害），Phase 4 实现
- **短期**：DM 手动扣血（现有 modify_value），伤害字段预留

### 10.4 墙的形态
- **决策**：半格视觉墙（碰撞不变），邻居感知朝向，读 `wall_render="solid"`
- **不做线段墙**：格子制视野引擎刚修好，重写代价太大

### 10.5 烟雾（单一数据源）
- **决策**：`is_smoke` 是烟雾的唯一真相，`blocks_vision` 不重复存储
- `is_vision_blocking` 直接判断 `cell.is_smoke`（ADR-4）
- TTL 过期后只需清 `is_smoke`，不用同步更新 `blocks_vision`
