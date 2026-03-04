from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import init_db
from seed_questions import seed
from routers import auth, events, guests, matching, websocket, admin, host


async def _seed_admin():
    """Create default admin user from env vars if no admin exists yet."""
    from config import ADMIN_EMAIL, ADMIN_PASSWORD
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        return
    from services.auth_service import get_user_by_email, create_user
    existing = await get_user_by_email(ADMIN_EMAIL)
    if not existing:
        await create_user(
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            display_name="Admin",
            role="admin",
        )
        print(f"Admin-Benutzer erstellt: {ADMIN_EMAIL}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await seed()
    await _seed_admin()
    # Cleanup expired sessions on startup
    from services.auth_service import cleanup_expired_sessions
    await cleanup_expired_sessions()
    yield


app = FastAPI(title="Matchbox", lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(auth.router)
app.include_router(events.router)
app.include_router(guests.router)
app.include_router(matching.router)
app.include_router(websocket.router)
app.include_router(admin.router)
app.include_router(host.router)


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
