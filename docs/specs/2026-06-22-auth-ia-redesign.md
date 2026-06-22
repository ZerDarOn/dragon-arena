# Dragon Arena — 账号与 IA 重构增量设计

**日期**: 2026-06-22
**性质**: 基于 [2026-06-22-dragon-arena-design.md](./2026-06-22-dragon-arena-design.md) 的增量设计
**目标**: FVTT 风格渐进式 IA：登录 → 工作台（聊天+沙盒） → 战役房间

---

## 背景

MVP 已完成后端全部 + 前端骨架。用户提出新的 IA 要求：

1. 登录页：历史用户列表 + 密码 + 管理员/玩家分支
2. 工作台（默认页）：聊天（大厅+私聊）+ 装饰性沙盒地图
3. 战役房间（加入后激活）：新增 战役大厅 / 空间 / 战争大厅 三频道
4. 玩家列表（含积分排名）、行动顺序抽签、角色卡（所有人通用）
5. 管理员额外：DMConsole + 创建战役 + 预建账号

**安全模型**：私下使用 + 开隧道联机，不搞网络门禁；但要有**身份锁**——密码对了才能用这个身份，防止偷看别人底牌。

---

## ADR 汇总

### ADR-8 账号存储：SQLite + bcrypt
- **Decision**: SQLite 持久化 users 表，bcrypt 哈希密码
- **Context**: 防止玩家偷登他人身份看 secret_backups
- **Options**: (A) 纯前端 localStorage 门禁；(B) SQLite+bcrypt；(C) JWT+Postgres
- **Chosen**: B — bcrypt 防泄漏，SQLite 零运维
- **Tradeoff**: 单文件 DB 不能多机部署 → 隧道联机场景下 host 一人托管，可接受
- **Rollback**: 删除 `users.db` + 回退 schemas

### ADR-9 鉴权：JWT + Bearer
- **Decision**: 登录返回 JWT（24h TTL），所有 REST/WS 携带 `Authorization: Bearer <token>`
- **Context**: 无状态、易在 WS 握手时验证
- **Options**: (A) Session+Cookie；(B) JWT；(C) Basic Auth
- **Chosen**: B — WS 握手用 query param 传 token 方便
- **Tradeoff**: JWT 无法主动失效（无服务端黑名单） → 24h 后自动失效，必要时管理员可改密码（旧 hash 变 → 旧 token 仍有效但用不进去... 实际上 JWT 不查 DB，所以改密码不立即失效）
- **Mitigation**: TTL 设短（4h），玩家重新登录即可；MVP 阶段足够
- **Rollback**: 去掉 JWT 中间件

### ADR-10 注册策略：管理员预建账号
- **Decision**: 只有 is_admin=true 的用户能调 `/admin/users` 创建账号
- **Context**: 防止隧道地址泄露后陌生人自建账号
- **Options**: (A) 开放注册；(B) 管理员预建；(C) 注册+审核
- **Chosen**: B — 固定朋友圈场景，管理员一把建好
- **Tradeoff**: 新人加入需管理员手动建号 → 一次性，可接受
- **Rollback**: 改 is_admin 字段逻辑

### ADR-11 角色卡可见性：owner + admin 可见全字段，他人只见公开字段
- **Decision**: `GET /characters/{id}` 后端按 `owner_id == requester OR requester.is_admin` 判断，否则过滤 `secret_backups`
- **Context**: secret_backups 是底牌，不能被其他玩家看到
- **Options**: (A) 前端过滤；(B) 后端字段级过滤
- **Chosen**: B — 前端过滤不安全（接口可被直接调）
- **Rollback**: 改 response model

### ADR-12 历史登录：前端 localStorage
- **Decision**: localStorage 存 `{nickname, role, lastLoginAt}[]`，不存密码
- **Context**: 方便下次快速点击登录
- **Options**: (A) sessionStorage；(B) localStorage
- **Chosen**: B — 跨浏览器会话保留
- **Tradeoff**: 换设备/浏览器需重新输 → 私下使用场景可接受
- **Rollback**: 删 localStorage key

---

## 数据模型

### User（新）
```python
class User(BaseModel):
    id: str                      # UUID
    nickname: str                # UNIQUE
    password_hash: str           # bcrypt
    is_admin: bool = False
    created_at: int              # ms timestamp
    last_login_at: int = 0
```

### CharacterSheet（新）
```python
class CharacterSheet(BaseModel):
    id: str
    owner_id: str                # = User.id
    name: str                    # 角色名（可 ≠ nickname）
    gender: str = ""
    profession: str = ""
    talent: str = ""
    # 由 creation_points 分配
    hp_base: int = 100
    armor_base: int = 5
    ap_base: int = 2
    gold: int = 0
    backpack: list[str] = []
    equipment_slots: list[str | None] = [None] * 6
    skill_slots: list[str | None] = [None, None]
    # ⚠️ 私有字段：他人不可见
    secret_backups: list[str] = []
    created_at: int
    updated_at: int
```

### Player/Token 调整
- `Player.owner_id` 指向 `User.id`（原 `Player.id` 保留为会话内 ID）
- 加入战役时把所选 CharacterSheet 的基础值复制到 Token 初始化

### Channel 扩展
chat.channel 枚举新增：
- `campaign_hall` — 战役大厅（房间内全员）
- `war_hall` — 战争大厅（系统播报，仅管理员能发，玩家只读）
- `private` — 私聊（带 target_player_id）

原 `hall` 改名为 `global_hall`（跨房间大厅，工作台用）。

---

## 路由结构（前端）

```
/login           LoginView
                 ├─ 历史用户列表（点击填入 nickname）
                 ├─ nickname + password 输入
                 ├─ [登录] 按钮
                 └─ 登录失败提示

/workbench       WorkbenchView（默认页）
                 ├─ 顶栏：欢迎 {nickname} | [角色卡] | [加入战役] | ([创建战役] if admin) | [登出]
                 ├─ 左：ChatPanel（channels = ['global_hall', 'private']）
                 ├─ 右：SandboxView（Logo + 循环动画 + 标语）
                 └─ 角色卡模态：CharacterSheetEditor（预编辑模板）

/battle/:roomId  BattleView（GameView 重构而来）
                 ├─ 顶栏：房间名 | 大回合/子回合 | [离开战役]
                 ├─ 顶栏（admin only）：DMConsole
                 ├─ 左侧栏：PlayerList(含积分排名) + TurnOrder(抽签) + DiceRoller + ValueEditor + StatePanel
                 ├─ 中：GameCanvas
                 └─ 右侧栏：ChatPanel（channels = ['global_hall', 'private', 'campaign_hall', 'spatial', 'war_hall']）
```

路由守卫：未携带 JWT → 重定向 `/login`。

---

## 后端接口变更

### 新增
- `POST /auth/login` — `{nickname, password}` → `{token, user}`
- `GET /auth/me` — 校验 JWT → 返回 user
- `GET /admin/users` (admin) — 列出所有用户
- `POST /admin/users` (admin) — 创建用户 `{nickname, password, is_admin}`
- `DELETE /admin/users/{id}` (admin) — 删除用户
- `GET /characters` — 列出我的角色卡
- `POST /characters` — 创建角色卡
- `PUT /characters/{id}` — 更新（仅 owner）
- `DELETE /characters/{id}` — 删除（仅 owner）
- `GET /characters/{id}` — 查询（按可见性过滤 secret_backups）

### 调整
- `POST /rooms` — 现在需要 JWT，host_id 从 token 解出（不再从 body 传）
- `GET /rooms` — 仅返回当前用户参与的房间
- `WS /ws/{room_id}` — query 加 `token=...`，连接时校验
- `Player` 创建：WS 连接时从 JWT 解出 user，绑定到 Player.owner_id

### 数据库
SQLite 文件：`backend/data/users.db`（gitignore）
- `users` 表
- `character_sheets` 表
- 用 `aiosqlite` 异步访问

---

## 安全检查清单

| 接口 | 鉴权 | 可见性 |
|------|------|--------|
| POST /auth/login | 公开 | - |
| GET /auth/me | JWT | 自己 |
| GET /admin/users | JWT + is_admin | 全部 |
| POST /admin/users | JWT + is_admin | - |
| GET /characters | JWT | 自己的全字段 + 他人的公开字段 |
| GET /characters/{id} | JWT | owner/admin 见全字段，他人无 secret_backups |
| POST /rooms | JWT | - |
| WS /ws/{room_id} | JWT (query param) | - |

---

## 实施顺序

**Phase 1 — 后端账号系统**（可独立测试）
1. SQLite + users 表 + UserStorage
2. JWT 工具（签发/校验）
3. bcrypt 工具
4. /auth/login + /auth/me
5. /admin/users CRUD
6. FastAPI 依赖注入：get_current_user / require_admin

**Phase 2 — 角色卡系统**（依赖 Phase 1）
7. character_sheets 表 + CharacterSheetStorage
8. /characters CRUD（含可见性过滤）
9. 创建账号时可选分配默认角色卡

**Phase 3 — 前端登录 + 工作台**
10. auth store（JWT 持久化）
11. LoginView（历史列表 + 表单）
12. WorkbenchView（双栏布局）
13. SandboxView（Logo + 动画）
14. ChatPanel channels prop 化
15. CharacterSheetEditor 组件

**Phase 4 — 战役房间重构**
16. BattleView（GameView 改名 + 调整 channels）
17. WSClient 携带 token
18. PlayerList 加积分排名
19. TurnOrder 抽签 UI
20. 路由守卫

**Phase 5 — 验证**
21. 后端单元测试（auth/admin/characters）
22. 前端 npm run build
23. E2E 冒烟测试（登录→工作台→创建战役→加入→战斗）

---

## 开放问题（推迟到 V2）

- JWT 主动失效（黑名单）
- 密码修改、找回
- 角色卡模板导入/导出
- 战绩统计页
