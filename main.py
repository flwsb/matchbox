import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import init_db
from routers import events, guests, matching, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Matchbox", lifespan=lifespan)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(events.router)
app.include_router(guests.router)
app.include_router(matching.router)
app.include_router(websocket.router)


if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
