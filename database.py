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
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    min_age INTEGER,
    max_age INTEGER,
    current_round INTEGER NOT NULL DEFAULT 0,
    max_rounds INTEGER NOT NULL DEFAULT 3,
    clues_sent INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS guests (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events(id),
    name TEXT NOT NULL,
    gender TEXT CHECK(gender IN ('male', 'female', 'non-binary')),
    attracted_to TEXT CHECK(attracted_to IN ('male', 'female', 'everyone')),
    completed_questionnaire INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    age INTEGER,
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
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    round INTEGER NOT NULL DEFAULT 1,
    insights_json TEXT
);
"""

# Migrations for existing databases (idempotent)
MIGRATIONS = [
    "ALTER TABLE events ADD COLUMN min_age INTEGER",
    "ALTER TABLE events ADD COLUMN max_age INTEGER",
    "ALTER TABLE events ADD COLUMN current_round INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE events ADD COLUMN max_rounds INTEGER NOT NULL DEFAULT 3",
    "ALTER TABLE events ADD COLUMN clues_sent INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE guests ADD COLUMN age INTEGER",
    "ALTER TABLE matches ADD COLUMN round INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE matches ADD COLUMN insights_json TEXT",
]


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def _apply_migrations(db: aiosqlite.Connection):
    for sql in MIGRATIONS:
        try:
            await db.execute(sql)
        except Exception:
            pass  # Column already exists
    await db.commit()

    # Remove old CHECK constraint on events.status (needed for 'clues' status)
    cursor = await db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='events'"
    )
    row = await cursor.fetchone()
    if row and "CHECK(status IN" in row["sql"]:
        await db.execute("PRAGMA foreign_keys=OFF")
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS events_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('romantic', 'professional')),
                description TEXT,
                event_date TEXT NOT NULL,
                host_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                min_age INTEGER,
                max_age INTEGER,
                current_round INTEGER NOT NULL DEFAULT 0,
                max_rounds INTEGER NOT NULL DEFAULT 3,
                clues_sent INTEGER NOT NULL DEFAULT 0
            );
            INSERT OR IGNORE INTO events_new (id, name, event_type, description, event_date,
                host_name, status, created_at)
                SELECT id, name, event_type, description, event_date,
                    host_name, status, created_at FROM events;
            DROP TABLE events;
            ALTER TABLE events_new RENAME TO events;
        """)
        await db.commit()
        await db.execute("PRAGMA foreign_keys=ON")


async def init_db():
    db = await get_db()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
        await _apply_migrations(db)
    finally:
        await db.close()
