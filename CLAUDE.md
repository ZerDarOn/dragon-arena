# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Note: this `dragon-arena/` folder lives under `AiDome/临时/pvp/` only as a temporary storage
> location. It is its own independent git repository, unrelated to the AiDome or NagaAgent
> projects elsewhere in the workspace. Treat it as a standalone codebase.

## Project Overview

龙王争霸赛战棋平台 (Dragon Arena) — a networked tactical-grid platform built specifically for a
custom PvP battle-royale tabletop ruleset ("第一届龙王争霸赛"). One GM (团主) plays referee with a
god's-eye view; up to 8 players each control a token from their own device.

**Core philosophy** (see `docs/specs/2026-06-22-dragon-arena-design.md` for the full design doc):
- The platform provides interaction primitives (dice rolls, movement, value edits, messaging,
  visibility) — it does **not** adjudicate effects. Items/skills/traps/events are just cards with
  text; the GM reads the description and manually applies the outcome (e.g. HP loss). This is
  intentional: new content never requires code changes.
- All tunable numbers (vision range, AP costs, damage DCs, poison-circle timing, chat radius, etc.)
  are per-room config, not hardcoded — see `RoomConfig` in `backend/app/config.py`.
- Five distinct "library" types (traps/adventures/NPCs/monsters/events) are unified into one
  `MapEntity` model (entity + trigger condition + free-text effect description).

## Architecture

```
backend/        # FastAPI + WebSocket game server
  app/main.py       # REST routes: auth, admin, character sheets, rooms, actor library
  app/ws/handler.py # WebSocket protocol: RoomGameState wires together all per-room services
  app/services/     # One service per concern (room/token/turn/vision/chat/combat/map/dice/...)
  app/schemas/      # Pydantic models — wire format for REST + WS payloads
  app/deps.py       # JWT auth deps: get_current_user / require_admin / get_current_user_ws
frontend/       # Vue 3 + TS + Pinia + Canvas (battlefield rendering)
  src/stores/       # Pinia stores mirror backend domains (auth/room/chat/actors/resources/self)
  src/api/ws.ts     # WebSocket client, paired with backend/app/ws/handler.py protocol
docs/specs/     # Design docs (ADRs, data models, interaction flows) — read before changing rules
docs/plans/     # Implementation plans
```

**Backend composition root**: `RoomGameState` (`backend/app/ws/handler.py`) instantiates and wires
together `MapService`, `TokenService`, `VisionService`, `ChatService`, `TurnService`,
`EventLogService`, and `CombatEngine` per room — this is the place to look when tracing how a
WebSocket message flows through game logic. Combat/global effects (e.g. the poison circle / 毒圈)
are registered as rules (`RuleEntry` with `Trigger`/`Effect`) on `CombatEngine`, not hardcoded
branches — follow that pattern when adding new automatic global mechanics.

**Auth**: JWT bearer tokens. REST uses `Authorization: Bearer <token>`; WebSocket uses a `?token=`
query param (`get_current_user_ws`). User/character-sheet storage is a small SQLite layer
(`UserStorage`, default path `backend/data/users.db`, override via `DRAGON_ARENA_DB_PATH` env var
— tests set this to use an isolated DB). On first run with an empty user table, the server seeds a
default `admin`/`admin123` account (`_bootstrap_admin` in `main.py`).

**Visibility model**: most data is asymmetric — owners/admins see full character sheets (incl.
`secret_backups`); other players get the `*_to_public` / `sheet_to_public` filtered view. Game
state broadcasts are likewise per-viewer (fog of war / vision-filtered), with the GM always seeing
the unfiltered state. Keep this asymmetry in mind when adding new fields to schemas.

## Commands

### Backend (from `backend/`)

```bash
pip install -r requirements.txt   # fastapi, sqlalchemy, aiosqlite, python-jose, bcrypt, pytest...
uvicorn app.main:app --reload --port 8000

pytest                              # run all tests (asyncio_mode=auto, see pyproject.toml)
pytest tests/test_combat_engine.py  # single file
pytest -k test_name                 # single test by name

# Manual end-to-end checks against a running server (port 8000):
python e2e_smoke.py <room_id>   # basic WS flow: connect, place tokens, move, chat, dice
python e2e_full.py
python e2e_vision.py            # vision/fog-of-war specific
```

### Frontend (from `frontend/`)

```bash
npm install
npm run dev       # vite dev server
npm run build     # tsc + vite build
npm run preview
```

## Working with the ruleset

When changing combat/movement/vision/chat behavior, cross-check
`docs/specs/2026-06-22-dragon-arena-design.md` §6 (core interaction flows) and the ADR list (§13)
first — several behaviors that look like bugs are deliberate design decisions (e.g. spatial chat
has no persisted public history by design — ADR-2; sound is fully blocked by walls — ADR-6; COMBO
balance rules are soft warnings, never hard blocks — ADR-7).
