# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Matchbox is a real-time event matchmaking web application in Python. A host creates an event (romantic or professional/networking), shares a join link with guests, guests answer a Likert-scale questionnaire, and the host triggers a multi-round matching process with progressive clues and a synchronized WebSocket reveal. All user-facing text is in German.

## Tech Stack

- **Python 3.11** with FastAPI (async), Jinja2 templating, aiosqlite, Pydantic v2
- **SQLite** database (WAL mode, foreign keys enabled per connection)
- **SciPy/NumPy** for Hungarian algorithm matching
- **Alpine.js v3** + **PicoCSS v2** (loaded from CDN, no frontend build step)
- **WebSockets** (native FastAPI) for real-time reveal coordination
- **bcrypt** for password hashing, **itsdangerous** for session management

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Seed questions (required once before first use)
python seed_questions.py

# Start the server
python main.py
# or with auto-reload:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

App runs at http://localhost:8000. No test suite exists.

## Configuration (Environment Variables)

| Variable | Default | Description |
|---|---|---|
| `MATCHBOX_DB_PATH` | `./data/matchbox.db` | SQLite database path |
| `MATCHBOX_HOST` | `0.0.0.0` | Bind host |
| `MATCHBOX_PORT` | `8000` | Bind port |
| `MATCHBOX_SECRET_KEY` | (auto-generated) | Session/cookie secret |
| `MATCHBOX_SESSION_EXPIRY_HOURS` | `72` | Session lifetime |
| `MATCHBOX_ADMIN_EMAIL` | (none) | Seed admin account email |
| `MATCHBOX_ADMIN_PASSWORD` | (none) | Seed admin account password |

## Architecture

```
main.py                       # FastAPI app + lifespan (init_db, seed questions, seed admin, cleanup sessions)
config.py                     # Env var configuration
database.py                   # SQLite schema + migrations, get_db(), init_db()
models.py                     # Pydantic request/response models
seed_questions.py             # One-time script to seed the questions table

middleware/
  auth.py                     # get_current_user(), require_auth(), require_admin() dependencies

routers/
  auth.py                     # Login (/anmelden), register (/registrieren), logout (/abmelden)
  admin.py                    # Admin panel (/admin) — stats, user mgmt, event mgmt
  host.py                     # Host event list (/meine-events), event results
  events.py                   # Event creation, dashboard (owner/admin-restricted)
  guests.py                   # Guest join, questionnaire, answer submission
  matching.py                 # Match trigger, clue sending, reveal broadcast
  websocket.py                # WS /ws/event/{event_id}/{guest_id}

services/
  auth_service.py             # User CRUD, bcrypt hashing, session management
  event_service.py            # Event CRUD, admin stats, cascading delete
  guest_service.py            # Guest/question/answer CRUD
  matching_service.py         # Compatibility scoring, Hungarian assignment, clue generation
  connection_manager.py       # In-memory WebSocket rooms, countdown, reveal broadcast

templates/                    # Jinja2 HTML (German UI)
  auth/                       # login.html, register.html
  admin/                      # layout.html, dashboard.html, users.html, events.html
  host/                       # my_events.html, event_results.html
  base.html, dashboard.html, index.html, join.html, questionnaire.html, reveal.html, icons.html
static/css/styles.css         # Design system with light/dark mode
```

## Database Schema

Seven tables defined in `database.py`:
- **users** — email (unique), password_hash (bcrypt), display_name, role (`host` | `admin`), is_active flag
- **sessions** — session tokens with expiry, IP address, user agent tracking
- **events** — event metadata; status: `open | closed | matching | clues | revealed`; type: `romantic | professional`; `owner_id` FK to users; multi-round fields: `current_round`, `max_rounds`, `clues_sent`; optional `min_age`/`max_age`
- **guests** — per-event guests with optional gender/attraction (for romantic events)
- **questions** — seeded question bank; event_type: `romantic | professional | both`; has weight and reverse_scored flag
- **answers** — guest Likert responses (1-5 scale)
- **matches** — computed pairs with compatibility score, round number, match_type (`romantic | professional | friendship`), `insights_json` for detailed compatibility breakdown

Schema uses idempotent migrations for adding columns to existing databases.

## Authentication & Roles

- **Guests** have no accounts — identified by `guest_id` cookie per event
- **Hosts** register with email/password → `session_token` cookie (HttpOnly, SameSite=Lax, 72h expiry)
- **Admins** seeded via env vars or promoted by existing admins
- `middleware/auth.py` provides FastAPI dependencies: `get_current_user()` (optional), `require_auth()` (redirect to login), `require_admin()` (403 if not admin)
- Events with `owner_id` are restricted to their owner and admins; legacy events (NULL owner) remain open

## Matching Algorithm

Located in `services/matching_service.py`:

1. Computes pairwise compatibility (0.0–1.0) using weighted Likert similarity with conviction bonuses for `values` and `relationship` categories
2. For **professional** events: pools all guests into one assignment problem
3. For **romantic** events: only mutually compatible pairs (gender/attraction) are considered; unmatched guests are friendship-matched among themselves
4. Uses `scipy.optimize.linear_sum_assignment` (Hungarian algorithm) via symmetric-duplication trick for non-overlapping optimal pairing
5. **Multi-round**: previous pairs are excluded to prevent re-matching
6. **Clues phase**: 3 progressive clues (vague category → keyword-based → question-aligned) sent via WebSocket before reveal
7. **Insights**: detailed compatibility breakdown (category scores, top alignments, insight sentences) stored as JSON

## Event Lifecycle

1. Host creates event → status `open`, guests join and answer questionnaire
2. Host triggers matching → status `matching` → pairs computed → status `clues`
3. Host sends up to 3 progressive clues → WebSocket broadcasts to matched guests
4. Host triggers reveal → 10-second countdown → personalized match reveal via WebSocket → status `revealed`
5. For multi-round events: cycle repeats with new pairings (previous pairs excluded)

## Important Constraints

- **Single-process only.** `ConnectionManager` holds WebSocket state in memory — do not run with multiple uvicorn workers.
- **No test suite or CI/CD.**
- **DB connections are opened/closed per service call** (not pooled).
- **`data/`** directory is auto-created at startup.
- **German UI.** All user-facing text, routes (`/anmelden`, `/registrieren`, `/meine-events`), and error messages are in German.
