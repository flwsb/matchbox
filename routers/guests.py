from fastapi import APIRouter, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from models import GuestCreate, AnswersSubmit
from services.event_service import get_event
from services.guest_service import (
    create_guest, get_guest, get_questions_for_event, submit_answers,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/event/{event_id}/join", response_class=HTMLResponse)
async def join_page(request: Request, event_id: str):
    event = await get_event(event_id)
    if not event:
        return HTMLResponse("<h1>Event nicht gefunden</h1>", status_code=404)
    if event["status"] not in ("open",):
        return HTMLResponse("<h1>Dieses Event nimmt keine neuen Gäste mehr an.</h1>")
    return templates.TemplateResponse("join.html", {
        "request": request,
        "event": event,
    })


@router.post("/event/{event_id}/join", response_class=HTMLResponse)
async def form_join_event(
    request: Request,
    event_id: str,
    response: Response,
    name: str = Form(...),
    gender: str = Form(None),
    attracted_to: str = Form(None),
    age: int | None = Form(None),
):
    event = await get_event(event_id)
    if not event:
        return HTMLResponse("<h1>Event nicht gefunden</h1>", status_code=404)

    # Age validation
    min_age = event.get("min_age")
    max_age = event.get("max_age")
    if min_age is not None or max_age is not None:
        if age is None:
            return templates.TemplateResponse("join.html", {
                "request": request,
                "event": event,
                "error": "Bitte gib dein Alter an.",
            })
        if min_age is not None and age < min_age:
            return templates.TemplateResponse("join.html", {
                "request": request,
                "event": event,
                "error": f"Du erfüllst leider nicht die Altersanforderungen für dieses Event ({min_age}–{max_age or '∞'} Jahre).",
            })
        if max_age is not None and age > max_age:
            return templates.TemplateResponse("join.html", {
                "request": request,
                "event": event,
                "error": f"Du erfüllst leider nicht die Altersanforderungen für dieses Event ({min_age or '0'}–{max_age} Jahre).",
            })

    try:
        guest_id = await create_guest(
            event_id=event_id, name=name, gender=gender or None,
            attracted_to=attracted_to or None, age=age,
        )
    except Exception:
        return templates.TemplateResponse("join.html", {
            "request": request,
            "event": event,
            "error": "Dieser Name ist bereits vergeben. Bitte wähle einen anderen.",
        })

    redirect = RedirectResponse(
        url=f"/event/{event_id}/questionnaire", status_code=303
    )
    redirect.set_cookie(key="guest_id", value=guest_id, httponly=True)
    return redirect


@router.get("/event/{event_id}/questionnaire", response_class=HTMLResponse)
async def questionnaire_page(request: Request, event_id: str):
    guest_id = request.cookies.get("guest_id")
    if not guest_id:
        return RedirectResponse(url=f"/event/{event_id}/join")

    guest = await get_guest(guest_id)
    if not guest or guest["event_id"] != event_id:
        return RedirectResponse(url=f"/event/{event_id}/join")

    if guest["completed_questionnaire"]:
        return RedirectResponse(url=f"/event/{event_id}/reveal")

    event = await get_event(event_id)
    questions = await get_questions_for_event(event["event_type"])

    return templates.TemplateResponse("questionnaire.html", {
        "request": request,
        "event": event,
        "guest": guest,
        "questions": questions,
    })


@router.post("/event/{event_id}/answers")
async def submit_questionnaire(request: Request, event_id: str):
    guest_id = request.cookies.get("guest_id")
    if not guest_id:
        return RedirectResponse(url=f"/event/{event_id}/join", status_code=303)

    form = await request.form()
    answers = []
    for key, value in form.items():
        if key.startswith("q_"):
            qid = int(key.replace("q_", ""))
            answers.append({"question_id": qid, "value": int(value)})

    await submit_answers(guest_id, answers)
    return RedirectResponse(url=f"/event/{event_id}/reveal", status_code=303)


@router.get("/api/events/{event_id}/questions")
async def api_get_questions(event_id: str):
    event = await get_event(event_id)
    if not event:
        return {"error": "Event nicht gefunden"}
    questions = await get_questions_for_event(event["event_type"])
    return questions
