# 龙王争霸赛战棋平台 — 设计文档

> **日期**: 2026-06-22
> **状态**: 草案（待用户审阅）
> **作者**: A-Jie + 用户共创

---

## 一、项目定位

**一句话**: 专门为《第一届龙王争霸赛》这套PvP大逃杀规则做的联机战棋平台。

**是什么**: 团主当裁判（上帝视角），8名玩家各自设备操作棋子。平台提供交互原子（投骰/移动/改值/发消息），**不裁决效果**——所有效果由团主口胡结算。

**不是什么**: 不是通用VTT，不是Foundry插件，不是AI自动裁判。

---

## 二、核心哲学

### 2.1 工具只提供操作原子，不裁决效果

- 道具/技能/陷阱/奇遇/事件 = **带文字的卡片**，导入只存文本
- 平台不判断"破伤风该怎么扣血"，团主看描述 → 手动扣血
- 好处: 以后加再多内容都不用改代码，因为是人在算

### 2.2 所有数值都是可调参数

视野距离、移动距离、AP消耗、伤害公式、毒圈节奏、聊天半径……全部不写死。每个房间独立配置。

### 2.3 五个库 = 一种实体

陷阱/奇遇/NPC/怪物/事件本质都是"地图实体 + 触发条件 + 效果描述"，用统一的 MapEntity 模型表达。

---

## 三、技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| 前端 | Vue3 + TS + Canvas + Pinia | Canvas够画网格，复用AiDome栈 |
| 后端 | Python FastAPI + WebSocket | 规则计算+实时同步 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | 战报/快照/房间 |
| 卡片库 | Excel→JSON导入器 | 纯文本存储 |
| 语音 | WebRTC + 空间音频混音 | 文字+语音一起做 |
| 部署 | Docker | 一键起 |

---

## 四、架构总览

### 4.1 分层架构

```
┌─────────────────────────────────────────────────────┐
│  ① 空间社交层 (Spatial Chat)                         │
│  频道: 大厅(公共历史)/战斗(公共历史)/私聊(双方历史)    │
│       /空间正常/空间大喊 (无公共历史，发送时推送)      │
│  传播: 正常=视野半径，大喊=×2，不穿墙                  │
│  语音: WebRTC，空间音频混音                            │
└─────────────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────────────┐
│  ② 战场层 (Battlefield)                              │
│  地形层: 墙/草/烟雾/高低差（可编辑）                   │
│  MapEntity层: 陷阱/奇遇/NPC/怪物/事件（统一模型）      │
│  棋子层: 玩家+怪物+召唤物+尸体+掉落物                  │
│  视野: 扇形+射线，团主上帝视角                          │
└─────────────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────────────┐
│  ③ 全局修饰器栈 (Global Modifier Stack)              │
│  活跃事件/状态 = 带TTL的参数修饰器                     │
│  自动应用到所有数值计算（视野/伤害/AP/毒圈...）         │
│  每回合自动减TTL，归零移除                             │
└─────────────────────────────────────────────────────┘
                        ↕
┌─────────────────────────────────────────────────────┐
│  ④ 交互原子层 (Interaction Atoms)                    │
│  投骰/改数值/标状态/拖拽移动/消息/装备管理/卡片展示     │
│  全部参数可调                                         │
└─────────────────────────────────────────────────────┘

横切层 ─────────────────────────────────────────────
│  ⑤ 战报事件流: 全量记录 → 回放（任意视角）             │
│  ⑥ 联机同步: 操作权令牌 + 状态快照 + 断线重连          │
─────────────────────────────────────────────────────
```

### 4.2 模块职责

| 模块 | 职责 | 不做什么 |
|------|------|---------|
| Room | 房间生命周期、玩家加入/离开 | 不做匹配 |
| MapEditor | 地形绘制/实体放置 | 不做战斗结算 |
| Vision | 视野计算+迷雾渲染 | 不做可见性判定外的逻辑 |
| MapEntity | 统一实体管理（陷阱/奇遇/NPC/怪物/事件） | 不解析效果 |
| ModifierStack | 全局修饰器栈管理 | 不触发事件，只应用 |
| TurnEngine | 回合制操作权传递 | 不代玩家做决策 |
| Dice | 投骰原子 | 不判输赢 |
| Chat | 频道+空间传播 | 不存空间历史 |
| SnapshotStore | 状态快照+回放 | 不做预测/插值 |
| CardLibrary | 卡片库导入+展示 | 不解析效果 |

---

## 五、关键数据模型

### 5.1 MapEntity（统一地图实体，核心简化）

```typescript
interface MapEntity {
  id: string
  name: string
  type: 'trap' | 'adventure' | 'npc' | 'monster' | 'event'
  rarity: 'E' | 'D' | 'C' | 'B' | 'A' | 'S' | 'normal' | 'rare' | 'epic' | 'legendary'
  position: { x: number; y: number } | null  // event 可能无位置

  trigger: {
    type: 'step_on'        // 踩踏（陷阱）
        | 'interact'       // 主动交互（NPC/奇遇）
        | 'turn_end'       // 大回合结束（事件）
        | 'manual'         // 仅团主手动触发
        | 'auto'           // 条件满足自动触发
    condition_text: string                  // 纯文本，团主阅读判断
    condition_struct?: {                    // 可选，用于自动触发判定
      turn_min?: number
      turn_max?: number
      probability?: number
      killer_count_min?: number             // 如"击杀3人后触发"
    }
  }

  visibility: 'hidden'           // 仅团主可见（陷阱）
            | 'visible'          // 所有人可见（NPC/怪物）
            | 'public_broadcast' // 公开广播（事件）

  effect_text: string                      // 纯文本效果描述，系统不解析
  scope: 'single' | 'area' | 'global'
  area_radius?: number                     // scope=area 时

  // 事件专属: 全局修饰器
  global_modifiers?: GlobalModifier[]

  // 怪物专属: 棋子属性
  is_token?: boolean                       // 是否作为独立棋子存在
  stats?: {
    hp: number; armor: number; attack: number
    move: number; range: string
  }
  drop_text?: string                       // 掉落规则纯文本
}
```

### 5.2 GlobalModifier（全局修饰器）

```typescript
interface GlobalModifier {
  id: string
  source_entity_id: string                 // 来源事件
  source_name: string                      // 来源名称（展示用）

  param: 'vision_range'
        | 'damage_modifier'
        | 'armor_modifier'
        | 'ap_per_turn'
        | 'move_distance'
        | 'poison_rate'
        | 'poison_damage'
        | 'score_multiplier'
        | 'drop_multiplier'
        | 'skill_enabled'
        | 'allowed_actions'                // 白名单
        | 'shout_radius_multiplier'

  operation: 'add' | 'multiply' | 'set'
  value: number | string                   // allowed_actions 用 string[]

  ttl: number                              // 剩余回合数
  scope: 'all' | 'specific_players'
  target_players?: string[]                // scope=specific 时
}

// 计算时伪代码:
function computeParam(baseValue, target, paramName): any {
  let v = baseValue
  for (const mod of getActiveModifiers(target, paramName)) {
    if (mod.operation === 'add') v += mod.value
    if (mod.operation === 'multiply') v *= mod.value
    if (mod.operation === 'set') v = mod.value
  }
  return v
}
```

### 5.3 空间消息（无历史，发送时推送）

```typescript
interface SpatialMessage {
  id: string
  sender_id: string
  timestamp: number
  mode: 'normal' | 'shout'
  content_type: 'text' | 'audio'
  text?: string
  audio_url?: string                       // WebRTC 通道走实时流，文本走存储
  recipients: string[]                     // 发送时计算并固化
}

// 接收者只在自己"收件箱"里存一份
// 不存在"频道历史"概念
// 后加入范围的人看不到之前的消息
```

### 5.4 棋子（Player + Monster 共用）

```typescript
interface Token {
  id: string
  type: 'player' | 'monster' | 'summon' | 'corpse' | 'drop'
  owner_id?: string                        // player 的所有者
  position: { x: number; y: number }
  facing: 0..7                             // 0=北，顺时针
  hp: number; max_hp: number
  armor: number
  ap: number; max_ap: number
  gold: number
  score: number
  vision_range: number                     // 基础值，可被修饰器影响
  listen_radius: number                    // 听觉半径（含窃听加成）
  states: StateTag[]                       // 当前状态
  equipment_slots: string[6]               // 装备栏（卡片ID）
  skill_slots: string[2]                   // 技能槽
  backpack: string[]                       // 背包道具
  is_dead: boolean
  is_hidden: boolean                       // 隐身/潜行
}

interface StateTag {
  id: string
  name: string                             // 自定义名称，如"中毒"
  description: string                      // 团主可读
  ttl: number                              // 剩余回合数
  intensity?: number                       // 如中毒每回合扣几点
}
```

### 5.5 地图

```typescript
interface GameMap {
  width: number; height: number            // 格子数
  terrain: TerrainCell[][]                 // 二维数组
  safe_zone: { center: {x,y}; radius: number }  // 毒圈安全区
}

interface TerrainCell {
  x: number; y: number
  type: 'flat' | 'wall' | 'grass' | 'water' | 'high'
  height: number                           // 0/1/2，影响视野和射击
  smoke_ttl?: number                       // 烟雾持续回合
  is_smoke: boolean
}
```

---

## 六、核心交互流程

### 6.1 移动（拖拽轨迹，推导朝向）

```
1. 玩家按住自己棋子 → 开始拖拽
2. 实时显示:
   - 路径轨迹线（自己+团主可见）
   - 每格AP消耗
   - 总AP是否够（不够标红）
   - 路径是否遇墙（遇墙标红，不可达）
3. 松开 → 确认移动 → 棋子沿路径逐格移动
4. 每经过一格，检测 MapEntity trigger=step_on:
   - 命中 → 通知团主"Px踩到 [陷阱名]"
   - 团主决定是否触发 → 触发则弹出效果文字 → 团主手动结算
5. 移动完成 → 朝向 = 路径最后一段的方向（8方向枚举）
6. 广播视野更新（仅通知视野内玩家）
```

### 6.2 攻击（含防守抵消）

```
1. 攻击方选目标 → 系统计算距离 → 显示对应 DC（近8/中12/远16，可调）
2. 检测是否背后攻击（目标背后135°-180°扇区）
   - 是 → 标记"背后攻击，无法防守"
   - 否 → 继续
3. 攻击方投 D20 + Build修正（修正由团主口胡输入）
4. 判定:
   - D20=20 → 大成功（伤害×1.5）
   - D20=1 → 大失败（武器脱手等，团主判）
5. 防守环节:
   - 背后攻击 → 跳过防守
   - 正面 → 提示防守方"是否防守抵消？（消耗1AP）"
     - 防守（AP≥1）→ 投D(距离) → 最终命中值 = 攻击总分 - 防守投掷
       - 仍 ≥ DC → 命中
       - < DC → 闪避成功
     - 不防守/AP不足 → 直接结算
6. 命中结算:
   - 系统不计算伤害
   - 团主根据武器卡片文字手动扣血/标状态
7. 攻击方标记"暴露位置1回合"
```

### 6.3 事件触发（手动 + 自动）

```
【手动触发】
团主从事件库选事件 → 确认 →
  → 应用 global_modifiers 到栈 →
  → public_broadcast 广播事件描述 →
  → 战报记录

【自动触发】
每大回合结束:
  → 系统扫描所有 trigger.type='auto' 的事件
  → 检查 condition_struct（回合/概率/击杀数）
  → 条件满足:
     - 默认模式: 提示团主"事件X可触发，是否触发？" → 团主确认
     - 全自动模式: 直接触发，仅广播通知
  → 触发后同上流程

【修饰器TTL管理】
每大回合开始:
  → 所有活跃修饰器 ttl -= 1
  → ttl = 0 → 移除 → 参数自动恢复
```

### 6.4 空间聊天（关键: 无公共历史）

```
【发送】
玩家在空间频道输入文本/语音 →
系统计算传播:
  radius = (mode=='shout' ? vision_range*2 : vision_range)
  for each player p in room:
    if p == sender or p.is_dead: continue
    if distance(sender, p) > radius: continue
    if has_wall_between(sender, p): continue   // 射线检测
    if has_signal_interceptor(p): recipients.add(p)  // 窃听/拦截
    recipients.add(p)
→ 推送给 recipients（永久存在各自收件箱）
→ 不存公共历史

【历史访问】
- 大厅/战斗/私聊: 有公共/双方历史，随时翻
- 空间频道: 无公共历史，只有各自收件箱
- 后加入范围的人: 看不到之前的消息（关键防Bug设计）

【声音穿墙判定】
- 射线检测: 从 sender 中心到 receiver 中心
- 经过任意 wall 类型 cell → 阻断
- 经过 smoke/grass → 不阻断（只影响视野不影响声音）
```

### 6.5 视野计算

```
【扇形视野】
玩家朝向 facing (0..7)，每方向45°
- 正前±45°（1个45°扇区）: 视野半径内完全可见
- 侧面±90°（2个45°扇区）: 模糊，只可见3格（默认）
- 背后135°-180°（2个45°扇区）: 不可见

【射线投射】
从玩家位置向四周发射射线:
  - 射线遇 wall → 中断
  - 射线遇 smoke → 中断（除非有看穿技能）
  - 射线遇 grass → 可穿过但目标半遮挡（远射DC+2）
  - 射线长度 = computeParam(base_vision, player, 'vision_range')

【可见度分级】
- distance ≤ vision: 完全可见（位置/装备/大致血量）
- vision < distance ≤ vision*2: 方向感知（只知方向）
- distance > vision*2: 完全不可见

【团主上帝视角】
- 看全场所有实体
- 能看每个玩家的视野扇形（半透明叠加）
- 能看所有玩家的朝向（箭头）
- 能看所有频道消息（含私聊）
```

---

## 七、角色卡显现机制

### 7.1 默认可见性

| 对象 | 自己 | 团主 | 其他玩家 |
|------|------|------|---------|
| 基础信息（昵称/角色名/职业/天赋） | 完全 | 完全 | 视野内可见 |
| 当前属性（血/甲/AP/G/积分） | 完全 | 完全 | 仅大致血量百分比 |
| 装备栏 | 完全 | 完全 | 视野内可见已穿戴 |
| 背包道具 | 完全 | 完全 | 完全隐藏 |
| 技能/外挂 | 完全 | 完全 | 完全隐藏 |

### 7.2 侦察道具扩展（团主手动应用）

| 道具 | 效果 | 实现方式 |
|------|------|---------|
| 信息数据库 | 开局知所有敌人Build | 发送角色卡副本给装备者 |
| 透视术 | 看穿障碍/隐身 | 视野计算忽略墙/隐身 |
| 窃听 | 偷听5格内通讯 | listen_radius += 5 |
| 信号拦截器 | 拦截私聊 | 私聊副本推送 |
| 红外热像仪 | 看穿隐身 | 视野计算忽略隐身 |
| 全息雷达 | 扫描全图 | 临时上帝视角1回合 |

---

## 八、联机与状态同步

### 8.1 操作权令牌

```
- 服务器维护 current_actor 字段
- 只有 current_actor 能操作棋子
- 结束回合 → 服务器按行动轴传递令牌
- 团主可强制夺取/传递令牌
```

### 8.2 状态同步

```
- 每次操作 → 服务器生成新状态 → 广播
- 每个玩家收到的是"自己的视野过滤版"
- 团主收到的是"完整版"
- 断线重连 → 请求最新快照 → 恢复
```

### 8.3 快照机制（用于时间回溯）

```
- 每回合结束自动存快照
- 保留最近 N 回合（可调，默认10）
- 时间回溯技能 → 恢复指定回合快照（仅对使用者）
- 其他玩家不受影响
```

---

## 九、战报与回放

### 9.1 事件流记录

所有原子操作全部记录:
```typescript
interface GameEvent {
  timestamp: number
  turn: number              // 大回合
  sub_turn: number          // 子回合
  actor: string             // 操作者
  action: 'move' | 'attack' | 'dice' | 'modify_value'
        | 'add_state' | 'send_message' | 'equip' | 'trigger_entity'
        | 'apply_modifier' | 'end_turn' | 'revive' | 'death'
  target?: string
  params: any
  result?: any
}
```

### 9.2 回放功能

- 时间轴拖动
- 快进/暂停/逐事件步进
- 跳转到指定大回合
- 可切换任意玩家视角（看他当时看到了什么）
- 团主视角（看全场）
- 导出战报为文本/JSON

---

## 十、配置项总表（全部可调）

```yaml
map:
  width: 30              # 4人以下20，5-6人25，7-8人30
  height: 30
  vision_range: 6
  move_ap_cost: 1        # 1AP走多少格（大图=2）
  sprint_ap_cost: 2
  sprint_distance: 4     # 大图=6
  height_diff_enabled: true

poison:
  shrink_rate: 1         # 每 N 回合缩1格
  shrink_interval: 2
  damage_table: [3, 5, 8, 12, 18, 25]   # 按阶段递增

combat:
  start_hp: 100
  start_armor: 5
  start_ap: 2
  creation_points: 30
  dc_table: { melee: 8, mid: 12, ranged: 16 }
  crit_success: 20
  crit_fail: 1
  defend_ap_cost: 1

economy:
  creation_to_gold: 20
  kill_drop_gold: 50

score:
  kill: 30
  survive_per_turn: 2
  boss_kill: 30
  assist_ratio: 0.3
  ranking_table_8p: [40, 28, 20, 15, 10, 6, 3, 3]

chat:
  speak_radius: 6        # = vision_range
  shout_multiplier: 2
  sound_through_wall: false
  eavesdrop_bonus: 5

turn:
  time_limit_sec: 10     # 0=不限
  ap_regen: 2
```

---

## 十一、分期实施

### MVP（核心可玩）
1. 房间系统 + Excel导入器
2. 地图渲染（Canvas网格）+ 地形编辑（画墙/草/水）
3. 棋子放置 + 拖拽移动 + 轨迹显示
4. 视野计算（扇形+射线+迷雾）
5. 交互原子（投骰/改值/标状态）
6. 文字聊天（大厅/私聊/空间频道）
7. 回合制操作权传递
8. 战报记录

### V1（完整体验）
9. MapEntity统一系统（陷阱/奇遇/NPC/怪物放置+触发）
10. 全局修饰器栈 + 事件触发（手动+自动）
11. 角色卡显现 + 侦察/反侦察对应
12. 毒圈系统
13. 战报回放
14. 移动端适配

### V2（增强）
15. WebRTC语音 + 空间音频
16. 断线重连优化
17. 自动化规则（毒圈自动扣血等确定性规则）

---

## 十二、待澄清/未来扩展

- 地图模板库（预设几张地图）
- 自定义事件编辑器（团主自己写事件）
- 多房间并行（同时开多个团）
- 观战模式（非参赛者观看）
- 数据分析（胜率/Build统计）

---

## 十三、关键设计决策（ADR）

### ADR-1: 拖拽轨迹替代朝向设置
- **决策**: 朝向由移动路径最后一段自动推导，不单独设置
- **理由**: 简化交互，符合直觉
- **代价**: 原地不动时保持上次朝向（边缘情况）

### ADR-2: 空间消息无公共历史
- **决策**: 空间频道消息只在发送时计算接收者，不存公共历史
- **理由**: 防止"走过路过翻聊天记录"破坏秘密团
- **代价**: 玩家想翻看之前听到的内容，只能翻自己收件箱

### ADR-3: MapEntity 统一模型
- **决策**: 陷阱/奇遇/NPC/怪物/事件用同一数据结构
- **理由**: 五个库本质相同（实体+触发+效果），代码量减半
- **代价**: 模型字段较多，部分字段对某些类型无意义（用可选字段处理）

### ADR-4: 全局修饰器栈
- **决策**: 事件/状态通过"带TTL的修饰器"影响全局参数
- **理由**: 优雅处理临时修改，自动过期
- **代价**: 修饰器叠加顺序需明确（add→multiply→set，按声明顺序）

### ADR-5: 工具不裁决效果
- **决策**: 所有道具/技能/陷阱效果由团主口胡，平台不解析
- **理由**: 内容可无限扩展，不用改代码
- **代价**: 自动化程度低，团主工作量大（可接受，因为规则复杂度太高）

### ADR-6: 声音不穿墙
- **决策**: 声音传播遇墙完全阻断
- **理由**: 真实感，且让墙壁有真实战术价值
- **代价**: 复杂地图计算成本（射线检测）

### ADR-7: COMBO限制作为软警告
- **决策**: 26条平衡规则（同类不叠加/吸血上限/AP获取上限等）不硬阻断，仅作软警告
- **理由**: 团主有最终解释权，可能允许特例；硬阻断会卡死流程
- **代价**: 依赖团主自觉（可接受，因为团主权威是这套游戏的基石）

---

## 十三.5、补充流程

### 偷窃流程（规则76-78）

```
1. 玩家移动到目标相邻格 → 选择"偷窃"
2. 投 D20 ≥ 8 → 命中（偷窃成功）
3. 系统从目标背包随机选 1 件道具（非装备）→ 转移到偷窃者背包
4. 目标觉察判定（团主代投 D20）:
   - 偷窃者在目标正面: DC = 10
   - 偷窃者在目标背后: DC = 14
   - 偷窃者隐身: 自动视为背后 (DC=14)
5. 觉察结果:
   - 成功 → 目标获得免费反击 1 次（不耗AP）
     反击: D20 ≥ 8 命中 → 肉搏伤害 10 + (D20-8) - 护甲
   - 失败 → 目标浑然不觉，道具丢失
6. 偷来的道具使用需 1AP 掏出
7. 只能偷背包道具，不能偷已穿戴装备
```

### COMBO限制软警告

```
当玩家在 Build 构筑阶段或战中装备时:
  - 系统扫描已选卡片，按 26 条平衡规则检测
  - 命中规则 → 软警告提示（不阻断保存）:
    例: "你选了 2 件吸血类效果，同类限制为最多装备 2 个，请确认"
    例: "真实伤害类效果不可购买，当前为战前购买阶段"
  - 所有警告记录到战报，团主控制台高亮显示
  - 团主可事后强制要求玩家调整
```

### 距离DC与防守投掷表（可调）

| 距离 | 攻击DC | 防守投掷 |
|------|--------|---------|
| 1-2格（近身） | 8 | D2 |
| 3-6格（中距） | 12 | D6 或 D8（可调） |
| 7格+（远射） | 16 | D7 或 D10（可调） |

---

## 十四、假设

1. 玩家数量: 2-8人（默认8人赛）
2. 地图尺寸: 20×20 到 30×30
3. 网络环境: 宽带，可接受 100-500ms 延迟（回合制宽容）
4. 设备: PC + 移动端，主流浏览器
5. 团主有基本的电脑操作能力（拖拽/点击）
6. 卡片库从 Excel 导入，团主负责准备
