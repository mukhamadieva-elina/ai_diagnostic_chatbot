import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.deps import get_db
from schemas.chat import ContactsRequest, ReplyRequest, ReplyResponse, SessionStateResponse, StartResponse
from services import scenario_engine

router = APIRouter(prefix="/chat", tags=["chat"])


def _base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.post("/start", response_model=StartResponse)
async def start_chat(request: Request, db: AsyncSession = Depends(get_db)):
    """Создаёт новую сессию, возвращает приветствие и список сценариев."""
    session_id, greeting, scenarios = await scenario_engine.start_session(db)
    return StartResponse(session_id=session_id, message=greeting, scenarios=scenarios)


@router.post("/reply", response_model=ReplyResponse)
async def reply(
    body: ReplyRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Принимает ответ пользователя, возвращает следующее сообщение бота."""
    result = await scenario_engine.handle_reply(
        session_id=body.session_id,
        user_message=body.message,
        db=db,
        base_url=_base_url(request),
        background_tasks=background_tasks,
    )
    return ReplyResponse(
        message=result.message,
        status=result.status,
        report_url=result.report_url,
    )


@router.post("/contacts", response_model=ReplyResponse)
async def submit_contacts(
    body: ContactsRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Принимает контактные данные из модального окна и запускает генерацию отчёта."""
    result = await scenario_engine.submit_contacts(
        session_id=body.session_id,
        name=body.name,
        email=body.email,
        phone=body.phone,
        db=db,
        base_url=_base_url(request),
        background_tasks=background_tasks,
        client_timezone=body.timezone,
    )
    return ReplyResponse(
        message=result.message,
        status=result.status,
        report_url=result.report_url,
    )


@router.get("/session/{session_id}", response_model=SessionStateResponse)
async def get_session(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Возвращает текущее состояние сессии (для восстановления после перезагрузки)."""
    state = await scenario_engine.get_session_state(
        session_id=session_id,
        db=db,
        base_url=_base_url(request),
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return SessionStateResponse(**state)
