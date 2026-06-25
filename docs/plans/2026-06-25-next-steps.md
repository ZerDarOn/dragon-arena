# Dragon Arena 下一步任务清单

> 日期: 2026-06-25
> 前提: 后端 166 测试全绿，核心交互原子全部可用，骰子系统已切换为服务端权威模式。

---

## P0 — 阻断上线（必做）

### 1. 断线消息队列 + 乐观更新
- **文件**: `frontend/src/api/ws.ts`
- **现状**: `send()` 在断线时 `ws?.send` 静默丢失；UI 要等 `state_sync` 返回才更新
- **要做的**:
  - WSClient 加 `outgoingQueue`，断线时入队，重连后 flush
  - 关键操作（move/attack/end_turn）加乐观更新：本地先改 store，服务端校验后确认或回滚

### 2. Token 状态图标渲染（GameCanvas）
- **文件**: `frontend/src/components/board/GameCanvas.vue`
- **现状**: token 绘制循环画了头像+血条+朝向，但不画 `t.states`。挂点燃/中毒/隐身在地图上零视觉反馈
- **要做的**: 在 token 头像周围画状态图标环（参考 FVTT Token HUD）

### 3. 回合条信息密度提升
- **文件**: `frontend/src/components/sidebar/TurnOrder.vue`
- **现状**: 只显示序号+名字+死亡标记
- **要做的**: 加 HP 条、AP 剩余、状态图标（🔥点燃 ⚠️中毒 👁️隐身）。PVP 快节奏下需 1 秒读懂局面

### 4. 角色卡创造点硬校验
- **文件**: `frontend/src/components/sheets/CharacterSheetEditor.vue`
- **现状**: `onSave()` 只校验 name 非空，`usedCP > 30` 不阻止保存
- **要做的**: 超点时弹红色警告并阻止保存

---

## P1 — 正确性修复

### 5. 近战伤害复用命中骰 bug
- **文件**: `backend/app/services/combat_engine.py`
- **现状**: `create_attack_rule` 的 effect 链 `roll_dice(d20)` → `calc_hit` → `calc_damage(dice="D20-8")`，`calc_damage` 取 `context.dice_results[-1].value`（命中那颗 d20），命中与伤害完全正相关
- **要做的**: `calc_damage` 应重摇一颗伤害骰，不重复用命中骰

### 6. 坐标边界校验
- **文件**: `backend/app/ws/handler.py` — `place_unit`、`set_terrain` 分支
- **现状**: `int(x)` 不校验是否在 `map_width/height` 内
- **要做的**: 加边界检查，越界返回 error

### 7. handler.py 死代码清理
- **文件**: `backend/app/ws/handler.py`
- **现状**: `set_turn_order`/`shuffle_turn_order` 各定义两次（约 L466-480 和 L745-755），后者无 admin 校验且永远不可达
- **要做的**: 删除重复分支，保留 L466 带 admin 校验的版本

### 8. resize_map 保留地形
- **文件**: `backend/app/ws/handler.py` — `resize_map` 分支
- **现状**: 注释自承 "clears existing terrains"，团主编辑中会丢数据
- **要做的**: 重建 map 时尽可能保留重叠区域的地形数据

---

## P2 — 体验提升

### 9. 毒圈渲染修复
- **文件**: `frontend/src/components/board/GameCanvas.vue` (L434-440)
- **现状**: 注释说"用圆形挖去安全区"，需验证是否实际实现了挖洞逻辑
- **要做的**: 确认或补全毒圈外全红、安全区内透明的渲染

### 10. 掷骰加值自描述
- **文件**: `frontend/src/components/sidebar/DiceRoller.vue`
- **现状**: 显示 `1d20+5`，但不知道 `+5` 从哪来
- **要做的**: 显示来源 `+5 = 力量3 + 熟练2`

### 11. 头像上传安全
- **文件**: `backend/app/main.py` — 头像上传端点
- **现状**: 只信 `content_type`，不校验真实内容；文件永不清理
- **要做的**: 校验文件头魔数 + 限制文件大小 + 过期清理

### 12. 生产安全加固
- **文件**: `backend/app/main.py`、`backend/app/services/auth_service.py`
- **现状**: CORS `*`、JWT 默认密钥兜底、默认 admin/admin123
- **要做的**:
  - CORS 收紧为具体域名
  - JWT_SECRET 缺失时拒绝启动
  - 首次登录强制改密

---

## P3 — 内容/规则库（长线）

### 13. MapEntity 统一模型
- 设计文档 5.1：陷阱/奇遇/NPC/怪物/事件 5 种实体统一 data model
- 当前均未实现，可作为后续大版本内容

### 14. 战报回放
- 设计文档 9.2：时间轴拖动、快进/暂停、视角切换、导出
- 当前 `EventLogService` 只记录不展示
- 文件: `backend/app/services/event_log_service.py`、`frontend/` 待建

---

## 执行顺序建议

```
Phase 1（本周）: P0 #1 断线队列 + #2 Token状态图标 + #4 角色卡校验
Phase 2（下周）: P0 #3 回合条 + P1 #5 近战bug + #6 边界校验 + #7 死代码
Phase 3（后续）: P2 体验项 + P3 内容库
```

---

## 当前 base 状态

| 指标 | 数值 |
|------|------|
| Backend tests | 166 passed |
| Backend services | 14 |
| Frontend components | 16 Vue components |
| 并发锁 | ✅ asyncio.Lock |
| 房间持久化 | ✅ SQLite 快照（每动作落盘） |
| 回合时限 | ✅ 倒计时 + 超时自动 end_turn |
| 积分排名 | ✅ 淘汰顺序 + 排名表 |
| 骰子系统 | ✅ `dice-box-threejs` 服务端权威模式 |
