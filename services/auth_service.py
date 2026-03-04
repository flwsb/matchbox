import uuid
from datetime import datetime, timedelta

import bcrypt as _bcrypt

from config import SESSION_EXPIRY_HOURS
from database import get_db


def hash_password(plain: str) -> str:
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


async def create_user(email: str, password: str, display_name: str,
                      role: str = "host") -> str:
    user_id = str(uuid.uuid4())
    pw_hash = hash_password(password)
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO users (id, email, password_hash, display_name, role) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, email.lower().strip(), pw_hash, display_name.strip(), role),
        )
        await db.commit()
    finally:
        await db.close()
    return user_id


async def get_user_by_email(email: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email.lower().strip(),),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_user_by_id(user_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def authenticate_user(email: str, password: str) -> dict | None:
    user = await get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    # Update last_login
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET last_login = datetime('now') WHERE id = ?",
            (user["id"],),
        )
        await db.commit()
    finally:
        await db.close()
    return user


async def create_session(user_id: str, ip_address: str = "",
                         user_agent: str = "") -> str:
    session_id = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)).isoformat()
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO sessions (id, user_id, expires_at, ip_address, user_agent) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, user_id, expires_at, ip_address, user_agent),
        )
        await db.commit()
    finally:
        await db.close()
    return session_id


async def get_session(session_id: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        session = dict(row)
        if datetime.fromisoformat(session["expires_at"]) < datetime.utcnow():
            await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await db.commit()
            return None
        return session
    finally:
        await db.close()


async def delete_session(session_id: str):
    db = await get_db()
    try:
        await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
    finally:
        await db.close()


async def cleanup_expired_sessions():
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM sessions WHERE expires_at < datetime('now')"
        )
        await db.commit()
    finally:
        await db.close()


# --- Admin functions ---

async def get_all_users(offset: int = 0, limit: int = 50) -> list[dict]:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, email, display_name, role, is_active, created_at, last_login "
            "FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_user_count() -> int:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM users")
        row = await cursor.fetchone()
        return row["cnt"]
    finally:
        await db.close()


async def update_user_role(user_id: str, role: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET role = ? WHERE id = ?", (role, user_id)
        )
        await db.commit()
    finally:
        await db.close()


async def deactivate_user(user_id: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET is_active = 0 WHERE id = ?", (user_id,)
        )
        # Also delete their sessions
        await db.execute(
            "DELETE FROM sessions WHERE user_id = ?", (user_id,)
        )
        await db.commit()
    finally:
        await db.close()


async def activate_user(user_id: str):
    db = await get_db()
    try:
        await db.execute(
            "UPDATE users SET is_active = 1 WHERE id = ?", (user_id,)
        )
        await db.commit()
    finally:
        await db.close()
