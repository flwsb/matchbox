import aiosqlite
from config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('romantic', 'professional')),
    description TEXT,
    event_date TEXT NOT NULL,
    host_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'closed', 'matching', 'revealed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS guests (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    name TEXT NOT NULL,
    gender TEXT CHECK(gender IN ('male', 'female', 'non-binary')),
    attracted_to TEXT CHECK(attracted_to IN ('male', 'female', 'everyone')),
    completed_questionnaire INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(event_id, name)
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text_de TEXT NOT NULL,
    category TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('romantic', 'professional', 'both')),
    weight REAL NOT NULL DEFAULT 1.0,
    reverse_scored INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id TEXT NOT NULL REFERENCES guests(id),
    question_id INTEGER NOT NULL REFERENCES questions(id),
    value INTEGER NOT NULL CHECK(value BETWEEN 1 AND 5),
    UNIQUE(guest_id, question_id)
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL REFERENCES events(id),
    guest_a_id TEXT NOT NULL REFERENCES guests(id),
    guest_b_id TEXT NOT NULL REFERENCES guests(id),
    compatibility_score REAL NOT NULL,
    match_type TEXT NOT NULL CHECK(match_type IN ('romantic', 'professional', 'friendship')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()
