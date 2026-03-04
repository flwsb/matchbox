from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from middleware.auth import require_admin
from services.auth_service import get_all_users, get_user_count, update_user_role, deactivate_user, activate_user
from services.event_service import get_all_events, get_admin_stats, delete_event

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    user = await require_admin(request)
    stats = await get_admin_stats()
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": user,
        "stats": stats,
        "active_page": "dashboard",
    })


@router.get("/benutzer", response_class=HTMLResponse)
async def admin_users(request: Request):
    user = await require_admin(request)
    users = await get_all_users()
    return templates.TemplateResponse("admin/users.html", {
        "request": request,
        "user": user,
        "users": users,
        "active_page": "users",
    })


@router.post("/benutzer/{user_id}/rolle")
async def change_user_role(request: Request, user_id: str, role: str = Form(...)):
    await require_admin(request)
    if role in ("host", "admin"):
        await update_user_role(user_id, role)
    return RedirectResponse(url="/admin/benutzer", status_code=303)


@router.post("/benutzer/{user_id}/deaktivieren")
async def toggle_user_active(request: Request, user_id: str):
    current_user = await require_admin(request)
    # Prevent self-deactivation
    if user_id == current_user["id"]:
        return RedirectResponse(url="/admin/benutzer", status_code=303)
    # Toggle: we read the form to decide
    form = await request.form()
    action = form.get("action", "deactivate")
    if action == "activate":
        await activate_user(user_id)
    else:
        await deactivate_user(user_id)
    return RedirectResponse(url="/admin/benutzer", status_code=303)


@router.get("/events", response_class=HTMLResponse)
async def admin_events(request: Request, status: str | None = None):
    user = await require_admin(request)
    events = await get_all_events(status_filter=status)
    return templates.TemplateResponse("admin/events.html", {
        "request": request,
        "user": user,
        "events": events,
        "active_page": "events",
        "status_filter": status,
    })


@router.post("/events/{event_id}/loeschen")
async def admin_delete_event(request: Request, event_id: str):
    await require_admin(request)
    await delete_event(event_id)
    return RedirectResponse(url="/admin/events", status_code=303)
