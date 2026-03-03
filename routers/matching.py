import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.event_service import get_event, update_event_status
from services.guest_service import get_guest
from services.matching_service import run_matching, save_matches, get_match_for_guest
from services.connection_manager import manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/api/events/{event_id}/match")
async def trigger_matching(event_id: str):
    event = await get_event(event_id)
    if not event:
        return {"error": "Event nicht gefunden"}

    await update_event_status(event_id, "matching")
    matches = await run_matching(event_id, event["event_type"])
    await save_matches(matches)
    await update_event_status(event_id, "revealed")

    # Run countdown and reveal in background
    asyncio.create_task(
        manager.run_countdown_and_reveal(event_id, matches)
    )

    return {
        "status": "matching_started",
        "matches_count": len(matches),
    }


@router.get("/event/{event_id}/reveal", response_class=HTMLResponse)
async def reveal_page(request: Request, event_id: str):
    guest_id = request.cookies.get("guest_id")
    if not guest_id:
        return RedirectResponse(url=f"/event/{event_id}/join")

    guest = await get_guest(guest_id)
    if not guest:
        return RedirectResponse(url=f"/event/{event_id}/join")

    event = await get_event(event_id)
    if not event:
        return HTMLResponse("<h1>Event nicht gefunden</h1>", status_code=404)

    # If already revealed, show match directly from DB
    existing_match = None
    if event["status"] == "revealed":
        existing_match = await get_match_for_guest(event_id, guest_id)

    return templates.TemplateResponse("reveal.html", {
        "request": request,
        "event": event,
        "guest": guest,
        "existing_match": existing_match,
    })
