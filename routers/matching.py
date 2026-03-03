import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.event_service import (
    get_event, update_event_status, increment_round,
    update_clues_sent, reset_clues_sent,
)
from services.guest_service import get_guest
from services.matching_service import (
    run_matching, save_matches, get_match_for_guest,
    get_all_matches_for_guest, get_matches_for_round,
)
from services.connection_manager import manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.post("/api/events/{event_id}/match")
async def trigger_matching(event_id: str):
    event = await get_event(event_id)
    if not event:
        return {"error": "Event nicht gefunden"}

    current = event["current_round"]
    max_rounds = event.get("max_rounds", 3)
    if current >= max_rounds:
        return {"error": "Maximale Anzahl an Runden erreicht."}

    new_round = await increment_round(event_id)
    await update_event_status(event_id, "matching")

    matches = await run_matching(event_id, event["event_type"], round_number=new_round)
    if not matches:
        return {"error": "Nicht genügend Gäste für ein Matching."}

    await save_matches(matches, round_number=new_round)

    # Go to clues phase
    await update_event_status(event_id, "clues")
    await reset_clues_sent(event_id)

    # Notify guests that matching is done and clues phase has begun
    await manager.broadcast(event_id, {
        "type": "clues_phase",
        "round": new_round,
        "message": "Matching abgeschlossen! Hinweise folgen...",
    })

    return {
        "status": "matching_complete",
        "matches_count": len(matches),
        "round": new_round,
        "rounds_remaining": max_rounds - new_round,
    }


@router.post("/api/events/{event_id}/send-clue")
async def send_clue(event_id: str):
    """Host triggers sending the next clue to all guests."""
    event = await get_event(event_id)
    if not event or event["status"] != "clues":
        return {"error": "Event ist nicht in der Hinweis-Phase."}

    round_num = event["current_round"]
    clue_num = event.get("clues_sent", 0) + 1

    if clue_num > 3:
        return {"error": "Alle Hinweise wurden bereits gesendet."}

    matches = await get_matches_for_round(event_id, round_num)
    await manager.send_clues_to_all(event_id, matches, clue_num)
    await update_clues_sent(event_id, clue_num)

    return {"status": "clue_sent", "clue_number": clue_num}


@router.post("/api/events/{event_id}/reveal")
async def trigger_reveal(event_id: str):
    """Host triggers the final reveal after clues phase."""
    event = await get_event(event_id)
    if not event or event["status"] != "clues":
        return {"error": "Event ist nicht in der Hinweis-Phase."}

    round_num = event["current_round"]
    matches = await get_matches_for_round(event_id, round_num)

    await update_event_status(event_id, "revealed")

    asyncio.create_task(
        manager.run_countdown_and_reveal(
            event_id, matches, round_number=round_num
        )
    )

    return {"status": "reveal_started", "matches_count": len(matches)}


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
    all_matches = []
    if event["status"] == "revealed":
        existing_match = await get_match_for_guest(
            event_id, guest_id, round_number=event["current_round"]
        )
        all_matches = await get_all_matches_for_guest(event_id, guest_id)

    return templates.TemplateResponse("reveal.html", {
        "request": request,
        "event": event,
        "guest": guest,
        "existing_match": existing_match,
        "all_matches": all_matches,
    })
