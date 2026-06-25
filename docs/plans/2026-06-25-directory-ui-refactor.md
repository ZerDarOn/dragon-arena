# 统一内容侧栏（Directory）重构 — 信息架构规整

> 日期: 2026-06-25
> 状态: P0 进行中（其余阶段待 MainView 在途改动落地后再开）
> 参考: FVTT Sidebar Directory + Document Ownership；枭雄统一侧栏 + 权限分级

---

## ⚠️ 协作前提（必读）

`MainView.vue` / `DMConsole.vue` / `TurnOrder.vue` 当前**有未提交改动**（另一个 agent 正在做 turn-timer / 回合条 / CP 校验，见 `docs/plans/2026-06-25-next-steps.md`）。
本重构的核心（P2/P3）要重写 `MainView.vue`，**会和它撞车**。因此：

- **现在只做 P0**（只动 `api/rest.ts` + 两个 admin 组件，均不在在途集合内，零冲突）。
- **P1–P4 等对方的 MainView/DMConsole/TurnOrder 改动提交后再开**，或显式协调谁先谁后。

---

## 1. 诊断：三件正交的事被揉成了一坨

任何"内容面板"本质是三个独立维度：

1. **What** — 数据是什么（角色卡 / 角色 / 怪物 / 道具）
2. **Where** — 在哪显示（导航弹窗 / 战役侧栏）
3. **Who** — 谁能看/改（管理员 / 玩家）

现状把这三维**笛卡尔积**成了一堆定制组件，证据：

| 概念 | 入口 1 | 入口 2 | 重复 |
|---|---|---|---|
| 角色卡 | 导航→Modal `CharacterSheetEditor`(416行) | 战役右栏 `MiniSheetPanel`(97行) | 两个面 |
| 资源库 | 导航→Modal `ResourceManager`(553行) | 战役左栏 `MiniResPanel`(242行) | **两套组件做同一件事** |

- 铁证：头像上传 `fetch('http://…:8000/api/upload/avatar')` 在 `ResourceManager.vue:397` 与 `MiniResPanel.vue:169` **逐字节复制两遍**，且都绕过 auth store（硬编码 URL + 直接读 localStorage token）。
- 权限是满屏 `v-if="auth.isAdmin"` 的**二元硬分叉**，不是"每条目级"权限。
- `MainView.vue` 是 **1031 行上帝组件**，7 个弹窗显隐 boolean，所有功能平铺其中。

→ 加一种内容、换一个位置、调一次权限，都要再复制一个组件。这是病根。

## 2. 目标架构（仿 FVTT/枭雄）

**一个数据模型 × 一个侧栏 × 一个 per-entry 权限函数**，三维解耦、零复制：

1. **`<Directory>` 常驻侧栏**，Tab：`角色卡 | 角色/怪物 | 装备/道具 |（以后）表格/事件库/地图`。
   - **待机态、战役态都常驻**；战役态只是多亮起"拖到地图""购买"等动作。
   - 取代"待机弹窗 vs 战役侧栏"的分叉。
2. **`<EntryCard>` 共享条目卡**：任何条目点开都用它，按 `canEdit(entry, me)` 渲染可编辑 / 只读。
   - 取代 ResourceManager / MiniResPanel / MiniSheetPanel / CharacterSheetEditor 四份里重叠的表单+CRUD。
3. **`perm(entry, user)` 权限函数**取代散落的 `v-if=isAdmin`。
   - **复用后端已有的非对称可见性原语**（角色卡 owner/admin 看 `secret_backups`、其他人看 `*_to_public`），不要另造二元 admin 分叉。
   - 默认：GM = 全部可编辑；玩家 = 公共可见 + 自己的角色卡可编辑。
4. **导航栏只留 app 级**：返回大厅 / 用户管理 / 登出。"角色卡""资源管理"降级成侧栏 Tab。

> 这块也是**资产池建设的地基**：将来 RollTable / 事件库入库 / 地图，都是这个 Directory 的新 Tab，而不是又一个弹窗（见资产池讨论）。

## 3. 分阶段路径（每步可单独上线）

| 阶段 | 做什么 | 动到的文件 | 与在途冲突 | 风险 |
|---|---|---|---|---|
| **P0 去重**（进行中） | 头像上传抽成 `rest.uploadAvatar()`，干掉两处复制 + 硬编码 URL | `api/rest.ts`、`ResourceManager.vue`、`MiniResPanel.vue` | 无 | 极低，UX 不变 |
| **P1 权限原语** | 加 `composables/usePermission.ts` 的 `canEdit/canView(entry)`，替换内容区 `v-if=isAdmin` | 新文件 + 内容组件 | 低 | 低 |
| **P2 合面板** | ResourceManager+MiniResPanel→一个 `<Directory>`（Tab 化）；角色卡并入做 Tab；待机/战役都常驻 | **MainView.vue**、新 Directory | **高（撞 MainView）** | 中 |
| **P3 拆上帝组件** | 从 MainView 抽 `<EntryCard>`、乐观更新 composable、token-view 弹窗，MainView 退化成布局壳 | **MainView.vue** | **高** | 中 |
| **P4 导航瘦身** | 导航只留大厅/用户管理/登出 | MainView.vue | 中 | 低 |

## 4. P0 细节（本次实施）

新增 `rest.uploadAvatar(file): Promise<string>`（走统一 `API` const + auth store，浏览器自动设 multipart 边界，返回绝对 URL）；两个 admin 组件的 `onAvatarUpload` 改为调用它。不改任何 props / 调用方，MainView 无需变动 → 与在途改动零冲突。

验收：前端 `npm run build` 通过；两处头像上传行为不变。

## 5. 风险与边界

- **avatar_url 存绝对 URL** 是另一个数据味道（换域名/端口会失效），但属于另一条线，P0 不碰，保持行为一致。
- P2/P3 动 MainView 前必须确认在途改动已落地，避免合并地狱。
- 权限模型别在前端凭空造，对齐后端既有的 `*_to_public`/`secret_backups` 语义，否则前后端两套权限会打架。
