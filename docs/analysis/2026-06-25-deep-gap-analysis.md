# Dragon Arena 多维深度缺陷分析报告

> 基于对 Dragon Arena 源码（backend/app 全量 + frontend/src 关键模块）、FVTT dnd5e 开源代码、FVTT V14 路线图、以及通用多人在线游戏最佳实践的多轮对照分析。
> 分析时间：2026-06-25
> 方法论：源码静态审查 + 开源架构对照 + 公开行为特征推断（枭雄闭源）

---

## 0. 背景校准

用户最初的核心判断："我们没有 FVTT 那种模型，所以效果自动化不现实"。
经源码核查后**部分修正**：Dragon Arena 已经有半个 FVTT 模型（`combat_engine.py` 的 Trigger+Effect），但它是孤儿；真正的根因不是"没模型"，而是"已有的零件没接线"。规则书里那些"场面话"（10 秒决策/先报先得/创造点）本质是**可开关的配置**——但 70% 的旋钮在 `RoomConfig` 里定义了却没接 UI，是"配置僵尸"。

---

## 1. 架构层缺陷（最严重）

### 缺陷 A-1：状态系统三套并存，互不知情 ★★★★★

这是全项目**最严重的架构债**。同一个"状态"概念在三个地方各有一套实现：

| 位置 | 方法 | 职责 | 硬编码状态名 |
|---|---|---|---|
| [token_service.py:139](file:///d:/Code/dragon-arena/backend/app/services/token_service.py) | `tick_states()` | 只衰减 TTL，不触发伤害 | 无（最干净） |
| [turn_service.py:90-125](file:///d:/Code/dragon-arena/backend/app/services/turn_service.py) | `_tick_states()` | 衰减 TTL + 触发伤害 + 恢复属性 | 点燃/中毒/流血/撕裂/隐身/护甲降低 |
| [turn_service.py:131-151](file:///d:/Code/dragon-arena/backend/app/services/turn_service.py) | `add_state()` | 立即应用效果 | 撕裂/隐身/护甲降低/定身/沉默 |
| [combat_engine.py](file:///d:/Code/dragon-arena/backend/app/services/combat_engine.py) | `Effect(type="add_state")` | 通用数据驱动效果 | 无（设计正确） |

**后果**：
- 加一个新状态要改 2-3 个地方，漏掉一个就行为不一致。
- `_tick_states` 里恢复护甲硬编码 `t.armor = min(t.armor + 2, 5)`——这个 `5` 不是 `max_armor`，是魔法数字。
- 如果同时挂"撕裂-2"和"护甲降低-3"，恢复顺序错了数据就错乱，因为没有任何"原始值副本"。

**FVTT 的正确做法**：保留 `source data`（原始数据）和 `derived data`（派生数据）两层副本，ActiveEffect 只改派生层，移除效果时重算——永远不会错。FVTT V14 正在用 `DataField.persisted` 属性把这个分离做得更显式（参见 foundryvtt/foundryvtt#13460）。

**修复方向**：把 `combat_engine.Effect` 扶正为唯一真相源，给 `StateTag` 增加 `origin/mode/value/source_field` 字段，`_tick_states` 改成通用 effect resolver。

---

### 缺陷 A-2：房间状态零持久化，后端重启=归零 ★★★★★

[handler.py:42](file:///d:/Code/dragon-arena/backend/app/ws/handler.py) 的 `_game_states: Dict[str, RoomGameState]` 是**进程内字典**。
对照 [user_storage.py](file:///d:/Code/dragon-arena/backend/app/services/user_storage.py)：用户/角色卡/道具库都存了 SQLite，但 Room/Token/Map/回合状态完全没存。

**后果**：
- 后端崩溃/重启 → 当前对局全部丢失（玩家打了一小时，角色血量/位置/状态全没了）。
- 无法水平扩展（多实例间状态不共享）。
- 一个吃鸡游戏跑 30-60 分钟，中途崩一次就废了——生产不可用。

**参考**：所有成熟 VTT/在线游戏都有 checkpoint。CSDN 弱网优化攻略、lilbattle #41、tabletop-tracker #12 都把"状态快照 + 增量同步"列为必备。

**修复方向**：Room/Token 状态每回合或每动作快照到 SQLite，重启时从快照恢复。

---

### 缺陷 A-3：并发竞态裸奔 ★★★★

FastAPI 异步事件循环里，`RoomGameState` 的所有操作（attack/move/use_item）**没有任何锁**，只有 `connection_manager.broadcast` 加了锁。

**典型竞态场景**：
1. 玩家 A 和玩家 B 在同一 tick 同时 `attack` 同一个怪物 C。
2. 两个协程同时读到 `C.hp = 50`。
3. A 的 `target.hp -= 30` → C.hp = 20。
4. B 的 `target.hp -= 30` → C.hp = 20（A 的修改被覆盖，因为 B 读的是旧值）。

更糟的是 [turn_service.py:148](file:///d:/Code/dragon-arena/backend/app/services/turn_service.py) 的 `apply_poison_circle` 和 `_tick_states` 也是裸跑——回合结算时如果有人同时操作，状态会错乱。

**修复方向**：给 `RoomGameState` 加 `asyncio.Lock`，所有写操作串行化。或者更彻底，把 Room 状态改成事件溯源（event sourcing），所有操作是 append-only 事件。

---

## 2. 网络与体验层缺陷

### 缺陷 N-1：断线期间操作静默丢失 ★★★★

[ws.ts:91](file:///d:/Code/dragon-arena/frontend/src/api/ws.ts) 的 `send(msg)`：
```typescript
send(msg: ClientMessage) { this.ws?.send(JSON.stringify(msg)) }
```
`this.ws` 在断线期间是 `null`，`?.send` 静默失败——玩家以为点了"结束回合"，实际消息没发出去。

**有重连机制（指数退避到 10s）但缺**：
- 待发消息队列：断线期间的 send 应该入队，重连后 flush。
- 消息序列号/cursor：断线后服务端应该能告诉客户端"你错过的事件从 #1234 开始"，而不是暴力推全量 state_sync。
- 乐观更新：玩家点击移动后 UI 应该立刻动，而不是等服务端 state_sync 回来。

**业界标准做法**（来自 lilbattle #41 / tabletop-tracker #12 / mediory 乐观更新指南）：
```
玩家操作 → 本地立刻应用 → 发送到服务端 → 校验
  ├─ 成功：保持
  └─ 失败：回滚到权威状态 + 提示
```

**修复方向**：WSClient 加 outgoing queue + 重连 flush；关键操作（move/attack/end_turn）加乐观更新。

---

### 缺陷 N-2：回合决策时限是死字段 ★★★

[config.py:45](file:///d:/Code/dragon-arena/backend/app/config.py) `turn_time_limit_sec: int = 10` 全项目搜索结果：
- `main.py` 接收配置 ✅
- `api/types.ts` 声明类型 ✅
- **没有任何代码读取它来启动倒计时** ❌
- **前端 TurnOrder 组件没有任何倒计时 UI** ❌

用户原话："10 秒决策可以开关、调整时间。可以加。"——但**旋钮要做出来才算开关**。现在是配置僵尸。

**修复方向**：`turn_service.start_turn` 启动 asyncio 倒计时任务，超时自动 `end_turn`；前端回合条加倒计时显示 + "延长 10s" 按钮（admin only）。

---

### 缺陷 N-3：回合条信息密度过低 ★★★

[TurnOrder.vue](file:///d:/Code/dragon-arena/frontend/src/components/sidebar/TurnOrder.vue) 只显示序号+名字+死亡标记。对比成熟 VTT，回合条每个角色至少应有：
- 当前 HP 条（一眼看出谁快死了）
- AP 剩余（知道这回合能做几个动作）
- 状态图标（🔥点燃 ⚠️中毒 👁️隐身）
- 当前激活者的醒目高亮

PVP 快节奏（每回合 10 秒）下，玩家需要 1 秒内读懂局面。

---

## 3. 前端渲染缺陷

### 缺陷 F-1：Token 状态不画在地图上 ★★★★

[GameCanvas.vue 第411-440行](file:///d:/Code/dragon-arena/frontend/src/components/board/GameCanvas.vue) 的 token 绘制循环画了：头像、血条、朝向箭头、攻击高亮、选中边框。
**完全没画 `t.states`**。

数据层 `Token.states: List[StateTag]` 有完整数据，但 Canvas 不渲染。玩家挂了"点燃/中毒/隐身/撕裂"在地图上零视觉反馈，必须打开 StatePanel 侧栏才能看——PVP 节奏下不可接受。

**修复方向**：在 token 头像周围画状态图标环（参考 FVTT Token HUD 的 status effect badges）。

---

### 缺陷 F-2：毒圈渲染逻辑可疑 ★★

[GameCanvas.vue 第434-440行](file:///d:/Code/dragon-arena/frontend/src/components/board/GameCanvas.vue)：
```javascript
ctx.fillStyle = 'rgba(100, 0, 0, 0.15)'
ctx.fillRect(0, 0, cv.width, cv.height)  // 全屏盖红
// 再用圆形挖去安全区  ← 注释说要做，但读取范围内没看到实现
```
如果"挖洞"逻辑缺失或被注释，毒圈外区域会整个盖红而非只染圈外。需要核查后续代码。

---

## 4. 规则书机制落地率清单

| 规则书机制 | config 定义 | 后端实现 | 前端 UI |
|---|:---:|:---:|:---:|
| 30 创造点 Build | ✅ | ❌ 无校验 | ⚠️ 只显示不阻止 |
| 创造点换金币 `creation_to_gold=20` | ✅ | ❌ | ❌ |
| 8 人积分排名表 `ranking_table_8p` | ✅ | ❌ 无结算 | ❌ |
| 回合决策时限 `turn_time_limit_sec=10` | ✅ | ❌ 死字段 | ❌ |
| 击杀掉金 `kill_drop_gold=50` | ✅ | ✅ handler.py:403 | ❌ |
| 击杀积分 `score_kill=30` | ✅ | ✅ handler.py:402 | ❌ |
| 存活积分 `score_survive_per_turn=2` | ✅ | ❌ 未在 end_turn 累加 | ❌ |
| 毒圈收缩 | ✅ | ✅ turn_service.py:148 | ⚠️ 只画圈不算伤害可视化 |
| 距离 DC 8/12/16 | ✅ | ✅ combat_engine | ❌ |
| AP 系统 | ✅ | ✅ | ⚠️ 不在回合条显示 |
| 侦察/反侦察（45 道具）| — | ❌ 纯文本 | ❌ |
| 随机事件（47 条）| — | ❌ 无触发器 | ❌ |
| 陷阱（36 条）| — | ❌ 纯文本 | ❌ |
| 怪物（43 条）| — | ❌ 纯文本 | ❌ |
| 奇遇（48 条）| — | ❌ 纯文本 | ❌ |

**核心赛制（吃鸡排名）落地率：0%**——游戏跑完没有排名。规则书的"8 名按淘汰顺序给 40/28/20/15/10/6/3/3 分"完全没实现。

**角色卡 Build 校验**：[CharacterSheetEditor.vue 第240行 onSave()](file:///d:/Code/dragon-arena/frontend/src/components/sheets/CharacterSheetEditor.vue) 只校验 `name` 非空。`usedCP > 30` 不阻止保存——玩家可以填出 999 HP 的角色，团主只能线下核对。

---

## 5. 和 FVTT 的架构对照（核心差距）

| 维度 | FVTT | Dragon Arena | 差距性质 |
|---|---|---|---|
| **效果数据模型** | ActiveEffect: `{key, mode, value}`，mode 有 6 种 | `Effect.params: Dict`，无 mode 概念 | **架构级**：缺数据驱动语义 |
| **属性派生** | source data + derived data 分离，效果改派生层 | 直接改 `token.hp/armor`，无副本 | **架构级**：移除效果会错 |
| **效果来源** | `origin` 字段记录来自哪个 Item/Actor | StateTag 无 origin | 中等：无法追溯 |
| **效果叠加** | stackingRules（刷新/叠加/取最高）| 一刀切"同名刷新 TTL" | 中等：毒圈和玩家点燃会互相覆盖 |
| **持续时长** | `duration.seconds` + `duration.turns` 分离 | 只有 `ttl`（回合数）| 中等：无法做"30 秒加速" |
| **触发系统** | Rule Elements: Trigger + Predicates + Actions | combat_engine 有雏形但是孤儿 | 架构级：没接通 |
| **持久化** | 全量 IndexedDB / 服务端 | 用户/角色卡存了，房间状态零持久化 | 架构级 |
| **并发** | 单线程 + 操作队列 | 异步裸奔，仅广播有锁 | 架构级 |
| **断线恢复** | 客户端游标 + 服务端推缺失事件 | 重连暴力推全量 state_sync | 中等 |

**一句话总结**：FVTT 用 20 年把"数据驱动效果"打磨到 V14 还在改（Active Effects v2）；Dragon Arena 有同源思想但停在 30% 完成度，剩下 70% 是接线工作。

---

## 6. 和枭雄的对照（体验差距）

枭雄闭源，基于公开行为特征推断：

| 维度 | 枭雄做对的 | Dragon Arena 现状 |
|---|---|---|
| **角色卡表单** | 结构化 + 实时校验（超点红字、槽满禁用） | 平铺字段，超点不阻止保存 |
| **掷骰面板** | 点击"攻击"自动拼 `1d20+5 vs AC15`，显示 `+5` 来源 | dice_service 是纯表达式计算器，加值靠玩家手输 |
| **回合条** | 头像 + HP + AP + 状态图标 | 只有名字+序号 |
| **一键操作** | 把高频场景打包（"受到伤害"按钮、"附加状态"菜单）| 每个操作都要走完整 WS 往返 |
| **中文本地化** | 母语流畅 | 已有 |

枭雄的哲学是"低门槛打包"，FVTT 是"高自由度零件"。Dragon Arena 夹在中间——既有 combat_engine 的零件野心，又没把零件接线，也没把高频场景打包。

---

## 7. 修复优先级矩阵

按"影响游戏能否跑通 × 改动成本"排序：

### P0 — 阻断性（不修游戏没法上线）

1. **房间状态持久化（A-2）**：后端重启归零是生产级阻断。
2. **并发锁（A-3）**：多人同时操作 HP 会错乱，破坏公平性。
3. **积分排名系统**：吃鸡游戏的核心赛制，落地率 0%。

### P1 — 架构性（不修会持续欠债）

4. **状态系统三合一（A-1）**：统一到 combat_engine，给 StateTag 加 origin/mode/value。
5. **断线消息队列 + 乐观更新（N-1）**：玩家点"结束回合"静默丢失是体验灾难。
6. **Token 状态图标渲染（F-1）**：地图上看不到状态，PVP 不可玩。
7. **回合决策时限接线（N-2）**：把死字段激活成真旋钮。

### P2 — 体验性（提升品质感）

8. **回合条信息密度（N-3）**：加 HP/AP/状态。
9. **角色卡创造点硬校验**：超点阻止保存。
10. **掷骰加值自描述**：显示 `+5 = 力量3 + 熟练2`。
11. **存活积分累加**：`score_survive_per_turn` 接到 `end_turn`。

### P3 — 内容性

12. 事件库/陷阱库/怪物库从 txt 入库 + 触发器。
13. 侦察/反侦察道具的机制化。

---

## 8. 推荐执行顺序

**不要一次性重构**。按依赖关系：

```
Phase 1（地基）：A-2 持久化 + A-3 并发锁
  ↓ （这两项是其他一切的安全网）
Phase 2（核心赛制）：积分排名 + 回合时限接线
  ↓ （让游戏能"跑完一局"）
Phase 3（状态统一）：A-1 状态系统三合一
  ↓ （解锁后续所有状态相关功能）
Phase 4（体验）：F-1 状态图标 + N-1 断线队列 + N-3 回合条
  ↓ （让游戏"好玩"）
Phase 5（内容）：库入库 + 触发器
```

每个 Phase 完成后都是可上线的增量。

---

## 9. 可借鉴的开源代码

- **FVTT dnd5e PHB**（MIT 许可）：`github.com/foundryvtt/dnd5e`——ActiveEffect 的 changes/modes/duration 数据结构可以直接参考（不是抄代码，是抄数据模型设计）。
- **FVTT V14 Active Effects v2 RFC**：`foundryvtt/foundryvtt#13460`、`#5842`——`persisted` 字段分离原始值/派生值的设计，正好解决 Dragon Arena 状态恢复错乱的问题。
- **lilbattle #41**（gRPC streaming 多人同步）：本地优先 + 服务端校验 + WorldChanges 流，这套架构适合 Dragon Arena 的乐观更新改造。
- **tabletop-tracker #12**：cursor 持久化 + 指数退避 + online 事件触发同步，WSClient 改造的直接参考。

---

## 10. 结论

Dragon Arena 的根本问题**不是功能不够，是已有的零件没接线**：
- `combat_engine.py` 是半个 FVTT ActiveEffect，但是孤儿；
- `RoomConfig` 是全套赛制旋钮，但 70% 是死字段；
- `Token.states` 数据齐全，但前端不渲染；
- WSClient 有重连，但没消息队列和乐观更新；
- 房间状态有完整 schema，但零持久化。

用户说"我们没有 FVTT 那种模型"——**其实有了，只是没扶正**。把孤儿模块接线、把死字段激活、把裸奔的并发上锁、把内存状态落盘，就完成了从"积木散落"到"积木拼好"的转变。这不是重写，是**接线和去重**。
