"""
Движок сценария: ведёт сессию по шагам и формирует ответы бота.
Вся логика состояний живёт здесь — эндпоинты только передают данные.
"""
import asyncio
import logging
import uuid
from dataclasses import dataclass

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.connection import async_session_factory
from models.db import ChatSession, DialogEntry, GlobalSettings, Scenario, ScenarioStep, Report, ValidationSettings
from services import llm, pdf_generator, bitrix
from services.metrics import SESSIONS_STARTED, CONTACTS_SUBMITTED, REPORTS_GENERATED, REPORTS_FAILED

logger = logging.getLogger(__name__)

GREETING = (
    "Здравствуйте! Я AI-диагност от AI Booster. "
    "Я помогу вам структурировать ключевую бизнес-проблему и предложу первые шаги для её решения. "
    "Выберите проблему из ниже перечисленного списка:"
)

_CONTACT_PROMPTS = {
    "name": "Пожалуйста, укажите ваше имя:",
    "email": "Укажите ваш email:",
    "phone": "Укажите ваш номер телефона:",
}
_CONTACT_SEQUENCE = ["name", "email", "phone"]


@dataclass
class BotReply:
    message: str
    status: str           # question | collecting_contacts | generating | completed
    report_url: str | None = None


async def start_session(db: AsyncSession) -> tuple[uuid.UUID, str, list[dict]]:
    """Создаёт новую сессию и возвращает (session_id, greeting, scenarios_list)."""
    session = ChatSession(status="pending_scenario")
    db.add(session)
    # flush чтобы получить UUID до создания дочерних записей
    await db.flush()

    scenarios_result = await db.execute(
        select(Scenario).where(Scenario.is_active == True).order_by(Scenario.id)
    )
    scenarios = scenarios_result.scalars().all()
    scenarios_list = [{"id": s.id, "name": s.name} for s in scenarios]

    options_text = "\n".join(f"{i + 1}. {s.name}" for i, s in enumerate(scenarios))
    full_greeting = f"{GREETING}\n\n{options_text}"

    db.add(DialogEntry(
        session_id=session.id,
        step_index=None,
        bot_message=full_greeting,
        user_answer=None,
    ))
    await db.commit()
    SESSIONS_STARTED.inc()
    return session.id, full_greeting, scenarios_list


async def handle_reply(
    session_id: uuid.UUID,
    user_message: str,
    db: AsyncSession,
    base_url: str,
    background_tasks: BackgroundTasks | None = None,
) -> BotReply:
    """Главный обработчик ответа пользователя. Возвращает следующее сообщение бота."""
    session = await db.get(
        ChatSession,
        session_id,
        options=[selectinload(ChatSession.entries), selectinload(ChatSession.report)],
    )
    if session is None:
        return BotReply(message="Сессия не найдена. Начните новый диалог.", status="error")

    if session.status == "completed":
        report_url = f"{base_url}/api/v1/report/{session_id}" if session.report else None
        return BotReply(
            message="Ваш отчёт уже готов.",
            status="completed",
            report_url=report_url,
        )

    if session.status == "generating":
        return BotReply(
            message="Идёт генерация ИИ отчёта, пожалуйста подождите...",
            status="generating",
        )

    if session.status == "pending_scenario":
        return await _handle_scenario_selection(session, user_message, db)

    if session.status == "in_progress":
        return await _handle_step_answer(session, user_message, db, base_url)

    if session.status == "pending_contact":
        return await _handle_contact_collection(session, user_message, db, base_url, background_tasks)

    return BotReply(message="Неизвестный статус сессии.", status="error")


async def submit_contacts(
    session_id: uuid.UUID,
    name: str,
    email: str,
    phone: str,
    db: AsyncSession,
    base_url: str,
    background_tasks: BackgroundTasks | None = None,
    client_timezone: str | None = None,
) -> BotReply:
    """Принимает все контактные данные разом и запускает генерацию отчёта."""
    session = await db.get(ChatSession, session_id)
    if session is None:
        return BotReply(message="Сессия не найдена.", status="error")
    if session.status != "pending_contact":
        return BotReply(message="Неверный статус сессии.", status="error")

    session.contact_name = name.strip()
    session.contact_email = email.strip()
    session.contact_phone = phone.strip()
    session.pending_contact_field = None
    session.status = "generating"
    await db.commit()
    CONTACTS_SUBMITTED.inc()

    generating_message = "Идёт генерация ИИ отчёта, это займёт около минуты..."
    if background_tasks is not None:
        background_tasks.add_task(_run_generation_bg, session.id, base_url, client_timezone)
        return BotReply(message=generating_message, status="generating")
    return await _generate_and_finalize(session, db, base_url, client_timezone)


async def get_session_state(
    session_id: uuid.UUID,
    db: AsyncSession,
    base_url: str,
) -> dict | None:
    session = await db.get(
        ChatSession,
        session_id,
        options=[selectinload(ChatSession.scenario), selectinload(ChatSession.report)],
    )
    if not session:
        return None

    report_url = None
    if session.status == "completed" and session.report:
        report_url = f"{base_url}/api/v1/report/{session_id}"

    return {
        "session_id": session.id,
        "status": session.status,
        "scenario_name": session.scenario.name if session.scenario else None,
        "report_url": report_url,
    }


# --- Внутренние обработчики ---

async def _handle_scenario_selection(
    session: ChatSession,
    user_message: str,
    db: AsyncSession,
) -> BotReply:
    scenarios_result = await db.execute(
        select(Scenario)
        .where(Scenario.is_active == True)
        .options(selectinload(Scenario.steps))
    )
    scenarios = scenarios_result.scalars().all()

    # Поддерживаем выбор по номеру или по названию
    chosen: Scenario | None = None
    stripped = user_message.strip()
    if stripped.isdigit():
        idx = int(stripped) - 1
        if 0 <= idx < len(scenarios):
            chosen = scenarios[idx]
    else:
        for s in scenarios:
            if s.name.lower() == stripped.lower():
                chosen = s
                break

    if not chosen:
        options_text = "\n".join(f"{i + 1}. {s.name}" for i, s in enumerate(scenarios))
        return BotReply(
            message=f"Пожалуйста, выберите номер или название из списка:\n\n{options_text}",
            status="question",
        )

    if not chosen.steps:
        return BotReply(
            message="Для этого сценария ещё не настроены вопросы. Выберите другой.",
            status="question",
        )

    # Фиксируем выбор пользователя и переходим к первому шагу
    _update_last_entry_answer(session, user_message)

    session.scenario_id = chosen.id
    session.current_step_index = 1
    session.status = "in_progress"

    total_steps = len(chosen.steps)
    first_step = chosen.steps[0]
    db.add(DialogEntry(
        session_id=session.id,
        step_index=1,
        bot_message=first_step.message_text,
        user_answer=None,
    ))
    await db.commit()
    return BotReply(message=f"Вопрос 1 / {total_steps}\n{first_step.message_text}", status="question")


async def _handle_step_answer(
    session: ChatSession,
    user_message: str,
    db: AsyncSession,
    base_url: str,
) -> BotReply:
    # Валидация ответа через GigaChat (настройки из БД)
    vs = await _get_validation_settings(db)
    if vs and vs.enabled:
        current_question = _get_current_question(session)
        if current_question:
            answer_type = await llm.validate_answer(
                current_question, user_message, vs.classification_prompt
            )
            if answer_type == "TYPE1" and vs.type1_enabled:
                return BotReply(
                    message=vs.type1_message.replace("{question}", current_question),
                    status="question",
                )
            if answer_type == "TYPE2" and vs.type2_enabled:
                user_message = f"{user_message}\n{vs.type2_answer_tag}"

    # Фиксируем ответ на текущий шаг
    _update_last_entry_answer(session, user_message)

    steps_result = await db.execute(
        select(ScenarioStep)
        .where(ScenarioStep.scenario_id == session.scenario_id)
        .order_by(ScenarioStep.order_index)
    )
    steps = steps_result.scalars().all()
    total_steps = len(steps)
    current_index = session.current_step_index  # 1-based

    if current_index < total_steps:
        next_step = steps[current_index]  # current_index как 0-based указывает на следующий
        next_question_number = current_index + 1
        session.current_step_index = next_question_number
        db.add(DialogEntry(
            session_id=session.id,
            step_index=next_question_number,
            bot_message=next_step.message_text,
            user_answer=None,
        ))
        await db.commit()
        return BotReply(message=f"Вопрос {next_question_number} / {total_steps}\n{next_step.message_text}", status="question")

    # Все шаги пройдены — переходим к сбору контактов
    session.status = "pending_contact"
    session.pending_contact_field = "name"
    contact_prompt = _CONTACT_PROMPTS["name"]
    db.add(DialogEntry(
        session_id=session.id,
        step_index=None,
        bot_message=contact_prompt,
        user_answer=None,
    ))
    await db.commit()
    return BotReply(message=contact_prompt, status="collecting_contacts")


async def _handle_contact_collection(
    session: ChatSession,
    user_message: str,
    db: AsyncSession,
    base_url: str,
    background_tasks: BackgroundTasks | None = None,
) -> BotReply:
    field = session.pending_contact_field
    _update_last_entry_answer(session, user_message)

    if field == "name":
        session.contact_name = user_message.strip()
        session.pending_contact_field = "email"
        prompt = _CONTACT_PROMPTS["email"]
    elif field == "email":
        session.contact_email = user_message.strip()
        session.pending_contact_field = "phone"
        prompt = _CONTACT_PROMPTS["phone"]
    elif field == "phone":
        session.contact_phone = user_message.strip()
        session.pending_contact_field = None
        session.status = "generating"
        await db.commit()

        generating_message = "Идёт генерация ИИ отчёта, это займёт около минуты..."
        if background_tasks is not None:
            # Запускаем генерацию в фоне и сразу возвращаем сообщение
            background_tasks.add_task(_run_generation_bg, session.id, base_url)
            return BotReply(message=generating_message, status="generating")
        else:
            # Fallback: генерация в том же запросе (если BackgroundTasks не передан)
            return await _generate_and_finalize(session, db, base_url)
    else:
        prompt = _CONTACT_PROMPTS.get("name", "Укажите ваше имя:")

    db.add(DialogEntry(
        session_id=session.id,
        step_index=None,
        bot_message=prompt,
        user_answer=None,
    ))
    await db.commit()
    return BotReply(message=prompt, status="collecting_contacts")


async def _generate_and_finalize(
    session: ChatSession,
    db: AsyncSession,
    base_url: str,
    client_timezone: str | None = None,
) -> BotReply:
    session.status = "generating"
    await db.commit()

    try:
        # Формируем текст диалога для LLM
        entries_result = await db.execute(
            select(DialogEntry)
            .where(
                DialogEntry.session_id == session.id,
                DialogEntry.step_index.is_not(None),
            )
            .order_by(DialogEntry.step_index)
        )
        entries = entries_result.scalars().all()

        dialog_text = "\n".join(
            f"Вопрос: {e.bot_message}\nОтвет: {e.user_answer or '—'}"
            for e in entries
        )
        scenario = await db.get(Scenario, session.scenario_id)
        dialog_context = f"Сценарий диагностики: {scenario.name}\n\n{dialog_text}"

        # Загружаем глобальные настройки (дефолтный промт + текст следующего шага)
        global_settings: GlobalSettings | None = await db.get(GlobalSettings, 1)
        global_prompt = global_settings.default_system_prompt if global_settings else None
        next_step_text = global_settings.next_step_text if global_settings else ""

        # Итоговый промт = глобальный дефолт + промт сценария (если задан)
        llm_response = await llm.generate_report(
            dialog_text=dialog_context,
            scenario_prompt=scenario.system_prompt or None,
            global_default_prompt=global_prompt,
        )

        # Генерируем PDF в отдельном потоке (matplotlib блокирующий)
        pdf_path = await asyncio.to_thread(
            pdf_generator.generate_pdf,
            session_id=session.id,
            scenario_name=scenario.name,
            contact_name=session.contact_name or "",
            contact_email=session.contact_email or "",
            contact_phone=session.contact_phone or "",
            llm_response=llm_response,
            next_step_text=next_step_text,
            client_timezone=client_timezone,
        )

        # Сохраняем отчёт в БД
        report = Report(
            session_id=session.id,
            pdf_path=pdf_path,
            llm_response=llm_response,
        )
        db.add(report)
        session.status = "completed"
        await db.commit()
        await db.refresh(report)

        # Отправляем в Bitrix24 (в фоне — ошибки не блокируют ответ)
        try:
            deal_id = await bitrix.push_deal(
                contact_name=session.contact_name or "",
                contact_email=session.contact_email or "",
                contact_phone=session.contact_phone or "",
                scenario_name=scenario.name,
                pdf_path=pdf_path,
                session_id=str(session.id),
            )
            if deal_id:
                report.bitrix_deal_id = deal_id
                report.sent_to_bitrix = True
                await db.commit()
        except Exception as e:
            logger.warning("Bitrix24 push failed: %s", e)

        report_url = f"{base_url}/api/v1/report/{session.id}"
        REPORTS_GENERATED.inc()
        return BotReply(
            message=(
                "Отчёт готов! Вы можете скачать его по ссылке ниже. "
                "Спасибо за прохождение диагностики!"
            ),
            status="completed",
            report_url=report_url,
        )

    except Exception as e:
        logger.error("Ошибка генерации отчёта для сессии %s: %s", session.id, e)
        session.status = "in_progress"  # откатываем статус чтобы повторить
        await db.commit()
        REPORTS_FAILED.inc()
        return BotReply(
            message="Произошла ошибка при генерации отчёта. Попробуйте ещё раз.",
            status="error",
        )


def _update_last_entry_answer(session: ChatSession, answer: str) -> None:
    """Ставит ответ пользователя в последнюю запись диалога без ответа."""
    for entry in reversed(session.entries):
        if entry.user_answer is None:
            entry.user_answer = answer
            return


async def _get_validation_settings(db: AsyncSession) -> ValidationSettings | None:
    """Возвращает единственную строку настроек валидации (id=1)."""
    return await db.get(ValidationSettings, 1)


def _get_current_question(session: ChatSession) -> str | None:
    """Возвращает текст вопроса, на который пользователь сейчас отвечает."""
    for entry in reversed(session.entries):
        if entry.step_index is not None and entry.user_answer is None:
            return entry.bot_message
    return None


async def _run_generation_bg(session_id: uuid.UUID, base_url: str, client_timezone: str | None = None) -> None:
    """Фоновая задача: генерирует отчёт в отдельной DB-сессии после отправки ответа клиенту."""
    async with async_session_factory() as db:
        session = await db.get(ChatSession, session_id)
        if session is None:
            logger.error("Фоновая генерация: сессия %s не найдена", session_id)
            return
        await _generate_and_finalize(session, db, base_url, client_timezone)