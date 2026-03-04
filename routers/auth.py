from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from middleware.auth import (
    get_current_user, set_session_cookie, clear_session_cookie,
)
from services.auth_service import (
    authenticate_user, create_user, create_session, delete_session,
    get_user_by_email,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/anmelden", response_class=HTMLResponse)
async def login_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/meine-events", status_code=303)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/anmelden", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    user = await authenticate_user(email, password)
    if not user:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "E-Mail oder Passwort ist falsch.",
            "email": email,
        })

    session_token = await create_session(
        user_id=user["id"],
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    response = RedirectResponse(url="/meine-events", status_code=303)
    set_session_cookie(response, session_token)
    return response


@router.get("/registrieren", response_class=HTMLResponse)
async def register_page(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse(url="/meine-events", status_code=303)
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/registrieren", response_class=HTMLResponse)
async def register(
    request: Request,
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
):
    ctx = {"request": request, "display_name": display_name, "email": email}

    if password != password_confirm:
        return templates.TemplateResponse("auth/register.html", {
            **ctx, "error": "Passwörter stimmen nicht überein.",
        })

    if len(password) < 8:
        return templates.TemplateResponse("auth/register.html", {
            **ctx, "error": "Das Passwort muss mindestens 8 Zeichen lang sein.",
        })

    existing = await get_user_by_email(email)
    if existing:
        return templates.TemplateResponse("auth/register.html", {
            **ctx, "error": "Diese E-Mail-Adresse ist bereits registriert.",
        })

    user_id = await create_user(
        email=email,
        password=password,
        display_name=display_name,
    )

    session_token = await create_session(
        user_id=user_id,
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
    )
    response = RedirectResponse(url="/meine-events", status_code=303)
    set_session_cookie(response, session_token)
    return response


@router.post("/abmelden")
async def logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        await delete_session(session_token)
    response = RedirectResponse(url="/", status_code=303)
    clear_session_cookie(response)
    return response
