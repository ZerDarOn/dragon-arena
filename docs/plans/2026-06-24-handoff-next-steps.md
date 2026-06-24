# Dragon Arena 交接 — 给下一个 AI 的任务清单

> 日期: 2026-06-24
> 上一轮已完成: 修复 4 个已确认会导致崩溃/连接冻结的 bug（见下方"刚修好的"）。
> 本文档列出**还没修**但已经验证/分析过的问题，按优先级排好，照着做就行，不用重新发现问题。

## 刚修好的（不需要再看，仅供你理解上下文）

1. `backend/app/ws/handler.py`：消息循环里所有错误分支的 `break` 全部换成了 `continue`。
   之前任何一次被拒绝的操作（AP 不够 / 越权 / 目标不存在）都会让那个玩家的 WebSocket 读循环
   永久退出（不是报错，是直接失联，且 `ConnectionManager` 里的僵尸连接还会一直收到广播）。
2. `_log_event()` 补了 `result` 形参 —— 之前 `dice_roll`/`move` 一调用就因为传了未声明的
   `result=` kwarg 直接 `TypeError` 崩溃。
3. `Token` schema（`backend/app/schemas/room.py`）加了 `character_name: str = ""` 字段 ——
   之前 `place_unit` 给怪物/NPC 赋名字时是对 Pydantic 实例做未声明字段赋值，必崩
   （`ValueError: "Token" object has no field "character_name"`），这功能之前完全不可用。
4. 前端 `onSpawnActor`（`frontend/src/views/MainView.vue`）去掉了多余的 `JSON.stringify`
   套娃（`WSClient.send()` 自己会 stringify，外面又 stringify 一次会让后端收到字符串而不是
   dict，`data.get("type")` 直接 `AttributeError`）。同时给 `api/ws.ts` 的 `ClientMessage`
   联合类型补上了 `spawn_token` / `set_turn_order`，清掉了一堆本来没必要的 `as any`。

全部用 `python -c` 直接复现确认过崩溃再修的；backend `pytest` 106 个测试全过；
`vue-tsc --noEmit` 跑过，新增改动没有引入新的类型错误（项目里本来就有几个跟这次无关的预存
type error，axios 模块解析、`@/` 路径别名等，不在本次范围内，不用管）。

---

## P0 — 数据泄露（建议下一步先做这个，影响游戏公平性，玩家能在浏览器里直接看到）

**问题**：`backend/app/ws/handler.py` 的 `_send_state_to_player()` 对"视野内完全可见"的
token 是整段 `tk_data` 原样塞进去的（约第 605-609 行 `filtered_tokens[tk_id] = tk_data`），
没有像"被察觉但不可见"那一档（只露 `id`/`type`/`character_name`）一样做字段级裁剪。

设计文档 `docs/specs/2026-06-22-dragon-arena-design.md` §7.1 写得很清楚：
- 装备栏：其他玩家"视野内可见已穿戴"——这个目前对，因为全量下发了
- **背包道具：其他玩家"完全隐藏"——目前是错的，背包对任何视野内的人都可见**
- 技能/外挂：同样应该完全隐藏，目前也是全量下发

**要做的**：在 `_send_state_to_player()` 里，对非 `tid`（自己）也非管理员的可见 token，
裁掉 `backpack` / `item_charges` / `skill_slots` 这几个字段后再放进 `filtered_tokens`。
注意自己的 token（`tk_id == tid`）和管理员视角不要裁，团主需要看全。

可以写个对应测试：两个测试 client 互相可见时，断言 B 收到的 A 的 state_sync 里
`tokens[A].backpack` 不存在或为空，但 `tokens[A].equipment_slots` 正常存在。

---

## P1 — 死代码 / 双重实现，会误导后续维护

**问题**：`RoomGameState._register_poison_circle_rule()`（`handler.py` 第 38-49 行）往
`CombatEngine.global_rules` 注册了一条 `Trigger(type="on_turn_start")` 的"毒圈收缩"规则，固定
伤害 5。但 `CombatEngine.execute_action()` 只在 `attack` 消息里被调用，`Trigger.match()` 对
`on_turn_start` 的判断是 `context.action == "turn_start"`——这个字符串全代码库搜不到第二个
出现的地方，**这条规则永远不会触发，是死代码**。

真正生效的毒圈伤害走的是另一条路：`TurnService.apply_poison_circle()`，在 `end_turn()` 里
直接调用，伤害公式按距离算（`config.poison_circle_damage_base + (dist-radius)*per_dist`），
跟死代码里硬编码的"固定 5 点"完全不是一回事。

**要做的**（二选一，跟人讨论一下要哪种）：
- 方案 A（推荐，改动小）：直接删掉 `_register_poison_circle_rule()` 和它的调用，删掉
  `CombatEngine` 里 `on_turn_start` 这个永远用不到的 trigger 分支，把唯一一套实现
  （`TurnService`）保留为真相源。
- 方案 B（如果未来想让"规则引擎"统一管理包括毒圈在内的所有效果）：在 `TurnService.end_turn()`
  大回合结算时，真正调用一次 `combat_engine.execute_action()` 并传 `action="turn_start"`，
  把 `apply_poison_circle()` 里的逻辑迁移成 `Effect(type="poison_circle_damage")` 的具体实现，
  让两套统一成一套。工作量更大，等 P2 的"战斗规则引擎导入 Excel 规则"一起做可能更划算。

---

## P2 — `use_item` 关键词黑魔法，违反项目核心设计哲学

**问题**：`handler.py` 的 `use_item` 分支用中文子串匹配做自动判定
（`"急救" in item_name or "血瓶" in item_name or "治疗" in item_name` → 自动加血 20；
`"隐身" in item_name or "隐形" in item_name` → 自动隐身）。

这跟设计文档 ADR-5「工具不裁决效果，效果由团主口胡，平台只提供原子操作」的核心哲学**直接冲突**：
- 团主自己起的道具名只要不包含这几个词，系统毫无反应
- 包含了这几个词，系统会不受团主控制地自动加血/隐身，团主拦不住
- 这是目前代码里唯一一处"自动判定游戏效果"的地方，跟整个项目的设计哲学不一致

**要做的**：跟项目所有者确认到底要哪种：
1. 完全删掉这段关键词判断逻辑，`use_item` 只做"扣道具次数 + 广播一条`item_used`事件让团主知道
   谁用了什么"，加血/隐身等效果全部交给团主用已有的 `modify_value` / `add_state` 手动操作
   （消息已经支持，不需要新功能）。— 这是跟设计哲学最一致的做法，推荐。
2. 如果确实想要自动化，至少改成基于 Actor/Item 库里显式配置的 `effect_type` 字段，而不是
   字符串包含匹配——但这意味着要先有一个道具效果的 Compendium 系统（见下面 P4）。

---

## P3 — 并发写竞态（暂不确定影响大小，需要先复现再决定要不要修）

**问题**：所有 token 字段修改（`move`/`attack`/`modify_value`/`add_state`）都是直接改内存里的
Pydantic 对象，没有锁。同一个房间的不同玩家连接是并发的 asyncio 协程，理论上两个人同时对同一个
token 发 `modify_value` 会有竞态（after-you-after-me 互相覆盖）。

**建议**：先别急着加锁（加锁本身有成本，可能没必要）。先写一个并发测试：两个 WS client 同时对
同一个 token 发 10 次 `modify_value`，看最终 hp 是否等于预期（应该不等，因为读-改-写没有原子性）。
如果确实复现了明显的丢失更新，再考虑给 `RoomGameState` 加一个 `asyncio.Lock`，在
`handle_ws_connection` 里处理会修改 token 状态的消息类型时 `async with gs.lock:` 包一层。
不要无脑全局加锁，先量化一下真实影响（8 人本地对战，操作频率不算高，可能优先级没那么高）。

---

## P4 — 缺失的设计（不是 bug，是阶段性还没做的功能，按需排期）

1. **状态持久化**：`_game_states: Dict[str, RoomGameState]` 纯内存，`uvicorn --reload`
   触发热重载就会清空所有房间数据。开发阶段经常改代码 + 真人在线对战同时发生，这个问题会
   反复炸。最小可行方案：每次 `_broadcast_state` 之后顺手把 `room.model_dump()` 落盘成
   `backend/data/rooms/{room_id}.json`，启动时如果文件存在就恢复。不需要做成数据库，JSON
   快照就够 MVP 阶段用。设计文档 §8.3 本来就规划了快照机制，可以借这个机会一起做。
2. **Compendium Item 库**：装备/道具/技能目前只是字符串名字（`equipment_slots: List[str]`），
   没有真正的效果定义。`ResourceManager` 里的"装备池"只是 localStorage 字符串列表。如果要做，
   参考 Actor 库（`backend/app/services/user_storage.py` 的 `actors` 表）已经验证过的模式：
   单独一张表 + REST CRUD + 前端 Pinia store，不需要重新设计架构。
3. **Scene 系统**：当前所有 Token 都挂在一个 Room 上，没有"地图场景"概念。FVTT 的核心是
   Scene 独立管理自己的 Token 列表，地图可以切换。这是个有一定改动量的重构（`Room` 需要拆出
   一层 `Scene`，`game_map`/`tokens` 从 Room 移到 Scene 下），优先级放最后，等 MVP 验证过
   一轮真实对战再做。
4. **战斗规则引擎缺规则配置**：`CombatEngine`/`RuleEntry`/`Trigger`/`Effect` 框架已经搭好了
   （见 `backend/app/services/combat_engine.py`），但目前只有 `_register_default_attack_rules`
   里硬编码的 3 条默认规则（远程/近战/徒手），没有从 `pvp团_text.txt` / Excel 模板导入真实的
   武器/技能规则。这个工作量取决于规则数量，建议先问清楚要支持多少条规则、是否真的需要做成
   数据驱动还是先用代码硬编码几个就够用。

---

## 验证方式建议

继续按原来的验证清单走：
1. `cd backend && python -m pytest -q` 应该全过（106 个测试，现在的基线）
2. 起后端 `uvicorn app.main:app --reload --port 8000`，用 `e2e_smoke.py` / `e2e_full.py`
   跑一遍基本流程
3. 改完 P0（背包泄露）以后，建议加一个新测试文件 `tests/test_state_filtering.py`，
   两个 client 互相在视野内时断言 backpack 不可见，写完之后这条就再也不会被回归破坏
