# 🐉 Dragon Arena（龙王争霸赛）

专门为《第一届龙王争霸赛》这套 PvP 大逃杀桌面 RPG 规则做的联机战棋平台。

团主（GM）当裁判，上帝视角看全场；最多 8 名玩家各自用自己的设备操作棋子。平台只提供交互原子
（投骰 / 移动 / 改数值 / 发消息 / 视野计算），**不裁决任何效果**——道具、技能、陷阱、事件都是
带文字描述的卡片，具体怎么扣血、加什么状态，全部由团主看描述手动操作。这样以后加多少新内容都
不用改代码。

> 这不是通用 VTT，不是 Foundry 插件，也不是 AI 自动裁判——它只服务于这一套特定的 PvP 规则。

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 (`<script setup>`) + TypeScript + Vite + Pinia + Vue Router + HTML5 Canvas |
| 后端 | FastAPI + WebSocket + 原生 `sqlite3`（无 ORM）+ bcrypt + JWT |
| 通信 | REST（鉴权/角色卡/Actor 库）+ WebSocket（实时对战状态同步） |

## 快速开始

### 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

首次启动时，如果用户表为空，服务会自动创建一个默认管理员账号
（`admin` / `admin123`，可用 `DRAGON_ARENA_DEFAULT_ADMIN` / `DRAGON_ARENA_DEFAULT_PASSWORD`
环境变量覆盖）。**生产环境请登录后立刻改密码。**

跑测试：

```bash
pytest                              # 全部测试
pytest tests/test_combat_engine.py  # 单个文件
pytest -k test_name                 # 按名称跑单个测试
```

对一个正在运行的后端（默认 `:8000`）做端到端冒烟测试：

```bash
python e2e_smoke.py <room_id>   # 基础流程：连接、落子、移动、聊天、投骰
python e2e_full.py
python e2e_vision.py            # 视野/战争迷雾专项
```

### 前端

```bash
cd frontend
npm install
npm run dev       # 开发服务器，默认连接 ws://localhost:8000
npm run build     # tsc + vite build
npm run preview
```

## 项目结构

```
backend/
  app/main.py        # REST 路由：鉴权 / 管理员 / 角色卡 / 房间 / Actor 库
  app/ws/handler.py   # WebSocket 协议入口，RoomGameState 把各个 service 组装起来
  app/services/       # 每个游玩概念一个 service（房间/棋子/回合/视野/聊天/战斗/地图/投骰…）
  app/schemas/        # Pydantic 模型，REST + WS 的数据契约
  tests/               # pytest 套件
frontend/
  src/components/board/GameCanvas.vue   # 核心画布：渲染 + 拖拽/绘图/测距交互
  src/components/layout/DMConsole.vue   # 团主控制面板（地形笔刷/毒圈/迷雾/回合）
  src/components/admin/ResourceManager.vue  # Actor 库（角色卡模板）管理
  src/stores/          # Pinia store，按后端领域划分
  src/api/ws.ts        # WebSocket 客户端，与后端协议一一对应
docs/specs/           # 设计文档（数据模型、交互流程、关键设计决策 ADR）
docs/plans/           # 实施计划 / 阶段性交接记录
```

## 核心设计

- **统一实体模型**：陷阱 / 奇遇 / NPC / 怪物 / 事件本质都是"地图实体 + 触发条件 + 效果文字"，
  用同一个 `MapEntity` 结构表达，不分别建模。
- **全部数值可调**：视野距离、AP 消耗、伤害 DC、毒圈节奏、聊天半径……都是房间级配置
  （`backend/app/config.py` 的 `RoomConfig`），不写死在代码里。
- **战争迷雾 + 视野过滤**：每个玩家收到的 `state_sync` 都是按自己视野裁剪过的版本，团主收到的
  是完整未过滤版本。
- 详细的交互流程、数据模型和关键设计决策（ADR）见
  [`docs/specs/2026-06-22-dragon-arena-design.md`](docs/specs/2026-06-22-dragon-arena-design.md)。

## 当前状态

MVP 阶段，核心对战流程（房间/落子/移动/视野/投骰/聊天/回合制/Actor 库 spawn）已可用。
已知问题和后续计划见 [`docs/plans/2026-06-24-handoff-next-steps.md`](docs/plans/2026-06-24-handoff-next-steps.md)，
包括待修的可见性裁剪问题、死代码清理、并发竞态排查，以及 Scene 系统 / Compendium 道具库等
尚未实现的功能。
