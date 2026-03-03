import uuid
from database import get_db


async def create_event(name: str, event_type: str, description: str,
                       event_date: str, host_name: str) -> str:
    event_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO events (id, name, event_type, description, event_date, host_name) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, name, event_type, description, event_date, host_name)
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
