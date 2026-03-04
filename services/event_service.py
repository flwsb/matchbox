import uuid
from database import get_db


async def create_event(name: str, event_type: str, description: str,
                       event_date: str, host_name: str,
                       min_age: int | None = None, max_age: int | None = None,
                       max_rounds: int = 3,
                       owner_id: str | None = None) -> str:
    event_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO events (id, name, event_type, description, event_date, "
            "host_name, min_age, max_age, max_rounds, owner_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, name, event_type, description, event_date, host_name,
             min_age, max_age, max_rounds, owner_id)
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


async def get_events_by_owner(owner_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM events WHERE owner_id = ? ORDER BY event_date DESC",
            (owner_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_all_events(offset: int = 0, limit: int = 50,
                         status_filter: str | None = None) -> list[dict]:
    db = await get_db()
    try:
        if status_filter:
            cursor = await db.execute(
                "SELECT e.*, u.display_name as owner_name "
                "FROM events e LEFT JOIN users u ON e.owner_id = u.id "
                "WHERE e.status = ? ORDER BY e.created_at DESC LIMIT ? OFFSET ?",
                (status_filter, limit, offset),
            )
        else:
            cursor = await db.execute(
                "SELECT e.*, u.display_name as owner_name "
                "FROM events e LEFT JOIN users u ON e.owner_id = u.id "
                "ORDER BY e.created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_admin_stats() -> dict:
    db = await get_db()
    try:
        stats = {}
        for table, key in [("users", "total_users"), ("events", "total_events"),
                           ("guests", "total_guests"), ("matches", "total_matches")]:
            cursor = await db.execute(f"SELECT COUNT(*) as cnt FROM {table}")
            row = await cursor.fetchone()
            stats[key] = row["cnt"]

        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE status IN ('open', 'closed', 'matching', 'clues')"
        )
        row = await cursor.fetchone()
        stats["active_events"] = row["cnt"]
        return stats
    finally:
        await db.close()


async def delete_event(event_id: str):
    db = await get_db()
    try:
        # Delete in order respecting foreign keys
        await db.execute("DELETE FROM matches WHERE event_id = ?", (event_id,))
        await db.execute(
            "DELETE FROM answers WHERE guest_id IN "
            "(SELECT id FROM guests WHERE event_id = ?)", (event_id,)
        )
        await db.execute("DELETE FROM guests WHERE event_id = ?", (event_id,))
        await db.execute("DELETE FROM events WHERE id = ?", (event_id,))
        await db.commit()
    finally:
        await db.close()
