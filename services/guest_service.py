import uuid
from database import get_db


async def create_guest(event_id: str, name: str, gender: str | None = None,
                       attracted_to: str | None = None) -> str:
    guest_id = str(uuid.uuid4())
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO guests (id, event_id, name, gender, attracted_to) "
            "VALUES (?, ?, ?, ?, ?)",
            (guest_id, event_id, name, gender, attracted_to)
        )
        await db.commit()
    finally:
        await db.close()
    return guest_id


async def get_guest(guest_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM guests WHERE id = ?", (guest_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        await db.close()


async def get_questions_for_event(event_type: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM questions WHERE event_type = ? OR event_type = 'both' "
            "ORDER BY id",
            (event_type,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def submit_answers(guest_id: str, answers: list[dict]):
    db = await get_db()
    try:
        for answer in answers:
            await db.execute(
                "INSERT OR REPLACE INTO answers (guest_id, question_id, value) "
                "VALUES (?, ?, ?)",
                (guest_id, answer["question_id"], answer["value"])
            )
        await db.execute(
            "UPDATE guests SET completed_questionnaire = 1 WHERE id = ?",
            (guest_id,)
        )
        await db.commit()
    finally:
        await db.close()


async def get_guests_for_event(event_id: str) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM guests WHERE event_id = ?", (event_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_guest_answers(guest_id: str) -> dict[int, int]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT question_id, value FROM answers WHERE guest_id = ?",
            (guest_id,)
        )
        rows = await cursor.fetchall()
        return {row["question_id"]: row["value"] for row in rows}
    finally:
        await db.close()
