# Dragon Arena 多维度评估

> 日期: 2026-06-24
> 评估范围: `D:\Code\dragon-arena`(后端 ~3000 行 Python / 前端 ~5200 行 Vue+TS / 测试 ~1200 行,16 commits)
> 评估方式: 通读后端服务层、WS handler、前端 API/store/视图、测试、设计文档与交接清单;`pytest` 全量跑过(108 passed)。

## 评分总览

| 维度 | 评分 | 一句话 |
|------|------|--------|
| 架构设计 | ⭐⭐⭐⭐½ | 服务拆分干净,"平台只提供原语、不裁决效果"的哲学贯彻得好 |
| 文档/规范 | ⭐⭐⭐⭐⭐ | 设计文档 + ADR + 交接清单,远超同规模项目 |
| 测试 | ⭐⭐⭐⭐ | 108 测试全过,服务层覆盖充分;但缺并发/集成边界 |
| 代码质量 | ⭐⭐⭐½ | 整体清爽,handler.py 偏长且有死代码 |
| 正确性 | ⭐⭐⭐ | 有几个真实 bug(见下) |
| 安全 | ⭐⭐½ | 鉴权框架对,但有几处授权/配置漏洞 |
| 运维/部署 | ⭐⭐ | 纯内存状态,无持久化、无重连,离生产远 |

## 1. 架构(强项)

- **组合根模式干净**:`RoomGameState` 把 7 个 service 在每个房间内组装好,WS 消息流向一目了然。单一职责拆分(token/vision/chat/turn/combat/map)是教科书级的。
- **设计哲学落地到位**:`CombatEngine` 用 `Trigger`/`Effect`/`RuleEntry` 数据驱动,五种"图鉴"统一成 `MapEntity`,可调数值全在 `RoomConfig`。"新内容不需要改代码"的目标确实实现了。
- **可见性非对称模型严谨**:`_send_state_to_player` 按 viewer 定制 state,fog-of-war 关闭时也仍裁剪背包/技能,地形按可见格清空防 F12 偷看。`_strip_secret_fields` 说明交接文档里的 **P0 数据泄露已修复**(`test_state_filtering.py` 补上)。交接里的 P1(毒圈死代码)、P2(use_item 关键词黑魔法)也都已清理——当前 `use_item` 只扣次数+广播,符合 ADR-5。

## 2. 正确性问题

**a) 近战伤害复用了命中骰** — `combat_engine.py`
`create_attack_rule` 的 effect 链 `roll_dice(d20)` → `calc_hit` → `calc_damage(dice="D20-8")`。`calc_damage` 取 `context.dice_results[-1].value`,即命中那颗 d20,而非重摇。结果近战命中与伤害完全正相关。几乎肯定非设计意图。

**b) handler.py 死代码 / 重复分支** — `handler.py:298-316` 与 `493-500`
`set_turn_order`、`shuffle_turn_order` 各定义两次。前者带 admin 校验,后者无校验且永远不可达(顺序匹配先命中前者)。应删 493-500。

**c) `resize_map` 清空地形** — `handler.py:285-297`,注释自承 "clears existing terrains"。团主编辑中会丢数据。

**d) 坐标无边界校验** — `place_unit`/`set_terrain` 直接 `int(x)`,不校验是否在 `map_width/height` 内。

## 3. 安全问题(部署前必修)

| 问题 | 位置 | 风险 |
|------|------|------|
| `update_config` 只要登录即可改任意房间配置 | `main.py:232` | 无 host/admin 校验 |
| CORS `allow_origins=["*"]` | `main.py:21` | 生产应收紧 |
| JWT 默认密钥兜底 | `auth_service.py:17` | 忘设环境变量即用 dev 密钥,可伪造 admin token。生产应缺失即拒绝启动 |
| 默认 admin/admin123 + 明文打印 | `main.py:42-50` | 需强制首次改密 |
| 头像上传只信 content_type,不校验真实内容,文件永不清理 | `main.py:270` | 伪装文件 + 磁盘无限增长 |

WS 鉴权(`get_current_user_ws`)、`_can_control` 的 owner/admin 校验是对的。

## 4. 运维/持久化(最大短板)

- `room_service.rooms` 与 `_game_states` 全内存,热重载/重启即清零。交接 P4.1 已点名未做。建议 `_broadcast_state` 后落盘 `data/rooms/{id}.json`,启动恢复。
- 前端 `ws.ts` 无重连、无心跳,硬编码 `ws://...:8000`(无 wss、端口写死)。
- `requirements.txt` 的 `sqlalchemy`、`aiosqlite` 实际未用(裸 `sqlite3`),依赖冗余可删。

## 5. 测试 & 前端

- 测试 108 绿,服务层覆盖扎实,有 state_filtering 回归保护。缺口:并发写竞态(交接 P3,token 改动无锁)、WS 重连、端到端授权负例。
- 前端 `GameCanvas.vue`(997 行)、`MainView.vue`(756 行)是"上帝组件",建议拆分;另有预存 type error(`@/` 别名、axios 解析)待收尾。

## 优先级建议

**P0(上线前必做)**
1. 修 `update_config` 授权(限 host/admin)
2. 房间状态持久化(JSON 快照即可)
3. 生产强制 `DRAGON_ARENA_JWT_SECRET`,缺失拒绝启动

**P1**
4. 修近战"命中骰=伤害骰"bug
5. 删 handler.py 重复 turn_order 分支
6. 前端 WS 重连 + 心跳 + wss/端口可配置

**P2**
7. 坐标边界校验、`resize_map` 保留地形、头像上传校验+清理
8. 并发竞态先写复现测试再决定加锁
9. 清理未用依赖、拆分超大前端组件

## 总评

16 commit 的个人项目中少见的高质量——架构想清楚、文档比代码还认真、测试跟得上。短板集中在"从能演示到能上线":持久化、重连、几处授权/正确性 bug。做掉 P0 三项即具备真人小范围对战条件。
