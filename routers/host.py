from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from middleware.auth import require_auth
from services.event_service import get_events_by_owner, get_event, get_event_stats

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/meine-events", response_class=HTMLResponse)
async def my_events(request: Request):
    user = await require_auth(request)
    events = await get_events_by_owner(user["id"])

    upcoming = [e for e in events if e["status"] in ("open", "closed", "matching", "clues")]
    past = [e for e in events if e["status"] == "revealed"]

    return templates.TemplateResponse("host/my_events.html", {
        "request": request,
        "user": user,
        "upcoming": upcoming,
        "past": past,
    })


@router.get("/meine-events/{event_id}/ergebnisse", response_class=HTMLResponse)
async def event_results(request: Request, event_id: str):
    user = await require_auth(request)
    event = await get_event(event_id)
    if not event or event.get("owner_id") != user["id"]:
        return HTMLResponse("<h1>Kein Zugriff</h1>", status_code=403)
    stats = await get_event_stats(event_id)

    # Get matches for all rounds
    from services.matching_service import get_all_event_matches
    matches = await get_all_event_matches(event_id)

    return templates.TemplateResponse("host/event_results.html", {
        "request": request,
        "user": user,
        "event": event,
        "stats": stats,
        "matches": matches,
    })
