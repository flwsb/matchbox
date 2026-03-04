from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

from services.auth_service import get_session, get_user_by_id


COOKIE_NAME = "session_token"
COOKIE_MAX_AGE = 72 * 3600  # 72 hours


async def get_current_user(request: Request) -> dict | None:
    """Extract the current user from the session cookie. Returns None if not logged in."""
    session_token = request.cookies.get(COOKIE_NAME)
    if not session_token:
        return None
    session = await get_session(session_token)
    if not session:
        return None
    user = await get_user_by_id(session["user_id"])
    return user


async def require_auth(request: Request) -> dict:
    """Dependency that requires a logged-in user. Redirects to login if not."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/anmelden"})
    return user


async def require_admin(request: Request) -> dict:
    """Dependency that requires an admin user. Returns 403 if not admin."""
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/anmelden"})
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Nur Administratoren haben Zugriff.")
    return user


def set_session_cookie(response, token: str):
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response):
    response.delete_cookie(key=COOKIE_NAME)
