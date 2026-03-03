import uuid
from database import get_db


async def create_event(name: str, event_type: str, description: str,
                       event_date: str, host_name: str,
                       min_age: int | None = None, max_age: int | None = None,
                       max_rounds: int = 3) -> str:
    event_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO events (id, name, event_type, description, event_date, "
            "host_name, min_age, max_age, max_rounds) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, name, event_type, description, event_date, host_name,
             min_age, max_age, max_rounds)
        )
        await db.commit()
    finally:
        await db.close()
    return event_id


async def get_event(event_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        await db.close()


async def update_event_status(event_id: str, status: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE events SET status = ? WHERE id = ?", (status, event_id)
        )
        await db.commit()
    finally:
        await db.close()


async def get_event_stats(event_id: str) -> dict:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as total FROM guests WHERE event_id = ?", (event_id,)
        )
        row = await cursor.fetchone()
        total = row["total"]

        cursor = await db.execute(
            "SELECT COUNT(*) as completed FROM guests "
            "WHERE event_id = ? AND completed_questionnaire = 1", (event_id,)
        )
        row = await cursor.fetchone()
        completed = row["completed"]

        return {"total_guests": total, "completed_questionnaire": completed}
    finally:
        await db.close()


async def increment_round(event_id: str) -> int:
    db = await get_db()
    try:
        await db.execute(
            "UPDATE events SET current_round = current_round + 1 WHERE id = ?",
            (event_id,)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT current_round FROM events WHERE id = ?", (event_id,)
        )
        row = await cursor.fetchone()
        return row["current_round"]
    finally:
        await db.close()


async def update_clues_sent(event_id: str, count: int):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE events SET clues_sent = ? WHERE id = ?", (count, event_id)
        )
        await db.commit()
    finally:
        await db.close()


async def reset_clues_sent(event_id: str):
    await update_clues_sent(event_id, 0)
