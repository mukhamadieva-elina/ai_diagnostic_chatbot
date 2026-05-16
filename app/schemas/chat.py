import uuid

from pydantic import BaseModel


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


class ContactsRequest(BaseModel):
    session_id: uuid.UUID
    name: str
    email: str
    phone: str
    timezone: str | None = None


class SessionStateResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    scenario_name: str | None
    report_url: str | None = None