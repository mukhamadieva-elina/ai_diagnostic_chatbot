import uuid

from pydantic import BaseModel, EmailStr


class StartResponse(BaseModel):
    session_id: uuid.UUID
    message: str
    scenarios: list[dict]  # [{id, name}]


class ReplyRequest(BaseModel):
    session_id: uuid.UUID
    message: str


class ReplyResponse(BaseModel):
    message: str
    # question | collecting_contacts | generating | completed
    status: str
    report_url: str | None = None
    summary: str | None = None


class ContactsRequest(BaseModel):
    session_id: uuid.UUID
    name: str
    email: EmailStr
    phone: str
    timezone: str | None = None


class SessionStateResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    scenario_name: str | None
    report_url: str | None = None
    message: str | None = None
    summary: str | None = None