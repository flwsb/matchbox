# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Matchbox is a real-time event matchmaking web application in Python. A host creates an event (romantic or professional/networking), shares a join link with guests, guests answer a Likert-scale questionnaire, and the host triggers a synchronized reveal that shows each guest their best match via WebSocket with a countdown animation. All user-facing text is in German.

## Tech Stack

- **Python 3.10+** with FastAPI (async), Jinja2 templating, aiosqlite, Pydantic v2
- **SQLite** database (stored at `data/matchbox.db` by default)
- **SciPy/NumPy** for Hungarian algorithm matching
- **Alpine.js v3** + **PicoCSS v2** (loaded from CDN, no frontend build step)
- **WebSockets** (native FastAPI) for real-time reveal coordination

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

App runs at http://localhost:8000.

## Configuration (Environment Variables)

| Variable | Default | Description |
|---|---|---|
| `MATCHBOX_DB_PATH` | `./data/matchbox.db` | SQLite database path |
| `MATCHBOX_HOST` | `0.0.0.0` | Bind host |
| `MATCHBOX_PORT` | `8000` | Bind port |

## Architecture

```
main.py               # FastAPI app + lifespan (calls init_db)
config.py             # Env var configuration
database.py           # SQLite schema definition, get_db(), init_db()
models.py             # Pydantic request/response models
seed_questions.py     # One-time script to seed the questions table

routers/
  events.py           # Event creation, dashboard page
  guests.py           # Guest join, questionnaire, answer submission
  matching.py         # POST /api/events/{id}/match — triggers matching
  websocket.py        # WS /ws/event/{event_id}/{guest_id}

services/
  event_service.py    # DB CRUD for events
  guest_service.py    # DB CRUD for guests, questions, answers
  matching_service.py # Compatibility scoring + Hungarian assignment
  connection_manager.py # In-memory WebSocket rooms, countdown, reveal broadcast

templates/            # Jinja2 HTML templates (German UI)
static/css/           # Custom CSS (countdown, card flip 3D, confetti)
```

## Database Schema

Five tables defined in `database.py`:
- **events** — event metadata; status: `open | closed | matching | revealed`; type: `romantic | professional`
- **guests** — per-event guests with optional gender/attraction (for romantic events)
- **questions** — seeded question bank; event_type: `romantic | professional | both`; has weight and reverse_scored flag
- **answers** — guest Likert responses (1-5 scale)
- **matches** — computed pairs with compatibility score; match_type: `romantic | professional | friendship`

WAL mode and foreign keys are enabled per connection.

## Matching Algorithm

Located in `services/matching_service.py`:

1. Computes pairwise compatibility (0.0–1.0) using weighted Likert similarity with conviction bonuses for `values` and `relationship` categories
2. For **professional** events: pools all guests into one assignment problem
3. For **romantic** events: only mutually compatible pairs (gender/attraction) are considered; unmatched guests are friendship-matched among themselves
4. Uses `scipy.optimize.linear_sum_assignment` (Hungarian algorithm) via symmetric-duplication trick for non-overlapping optimal pairing
5. Saves matches to DB, then WebSocket-broadcasts a 10-second countdown followed by personalized reveal messages

## User Flow

1. Host visits `/` → creates event → redirected to dashboard `/event/{id}`
2. Host shares join link `/event/{id}/join`
3. Guest enters name (+ gender/attraction for romantic) → `guest_id` cookie set → questionnaire
4. Guest completes questionnaire → redirected to `/event/{id}/reveal` (waiting room)
5. Guest page connects WebSocket `/ws/event/{id}/{guest_id}`
6. Host clicks "Matching starten" on dashboard → `POST /api/events/{id}/match`
7. Server runs matching, saves results, broadcasts countdown, then sends each guest their match via WS

## Important Constraints

- **No authentication.** Anyone with an event UUID can access the dashboard.
- **Single-process only.** `ConnectionManager` holds WebSocket state in memory — do not run with multiple uvicorn workers.
- **No test suite or CI/CD.** There are currently no tests.
- **DB connections are opened/closed per service call** (not pooled). Acceptable for low-traffic use.
- **`data/`** directory is auto-created at startup.
