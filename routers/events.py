from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from models import EventCreate
from services.event_service import create_event, get_event, get_event_stats, update_event_status

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/api/events")
async def api_create_event(event: EventCreate):
    event_id = await create_event(
        name=event.name,
        event_type=event.event_type,
        description=event.description,
        event_date=event.event_date,
        host_name=event.host_name,
    )
    return {
        "event_id": event_id,
        "join_url": f"/event/{event_id}/join",
        "dashboard_url": f"/event/{event_id}",
    }


@router.post("/event/create", response_class=HTMLResponse)
async def form_create_event(
    request: Request,
    name: str = Form(...),
    event_type: str = Form(...),
    description: str = Form(""),
    event_date: str = Form(...),
    host_name: str = Form(...),
):
    event_id = await create_event(
        name=name, event_type=event_type, description=description,
        event_date=event_date, host_name=host_name,
    )
    return RedirectResponse(url=f"/event/{event_id}", status_code=303)


@router.get("/event/{event_id}", response_class=HTMLResponse)
async def event_dashboard(request: Request, event_id: str):
    event = await get_event(event_id)
    if not event:
        return HTMLResponse("<h1>Event nicht gefunden</h1>", status_code=404)
    stats = await get_event_stats(event_id)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "event": event,
        "stats": stats,
    })


@router.post("/api/events/{event_id}/close")
async def close_event(event_id: str):
    await update_event_status(event_id, "closed")
    return {"status": "closed"}
