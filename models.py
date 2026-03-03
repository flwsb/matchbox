from pydantic import BaseModel


class EventCreate(BaseModel):
    name: str
    event_type: str  # 'romantic' or 'professional'
    description: str = ""
    event_date: str
    host_name: str
    min_age: int | None = None
    max_age: int | None = None
    max_rounds: int = 3


class EventResponse(BaseModel):
    event_id: str
    join_url: str
    dashboard_url: str


class GuestCreate(BaseModel):
    name: str
    gender: str | None = None
    attracted_to: str | None = None
    age: int | None = None


class GuestResponse(BaseModel):
    guest_id: str
    questionnaire_url: str


class AnswerItem(BaseModel):
    question_id: int
    value: int  # 1-5


class AnswersSubmit(BaseModel):
    guest_id: str
    answers: list[AnswerItem]


class AnswersResponse(BaseModel):
    status: str
    reveal_url: str


class QuestionOut(BaseModel):
    id: int
    text_de: str
    category: str
    event_type: str
    weight: float
    reverse_scored: bool


class MatchOut(BaseModel):
    name: str
    compatibility_score: float
    match_type: str
    top_shared_values: list[str]
