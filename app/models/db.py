import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey,
    String, Text, UniqueConstraint, CheckConstraint, Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Scenario(Base):
    """Тип проблемы, которую диагностирует бот."""
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    # ID файла промта в хранилище GigaChat (заполняется автоматически при сохранении через админку)
    gigachat_file_id: Mapped[str | None] = mapped_column(String(200))

    steps: Mapped[list["ScenarioStep"]] = relationship(
        back_populates="scenario",
        order_by="ScenarioStep.order_index",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="scenario")

    def __str__(self) -> str:
        return self.name


class ScenarioStep(Base):
    """Один вопрос в сценарии (строго последовательные)."""
    __tablename__ = "scenario_steps"
    __table_args__ = (
        UniqueConstraint("scenario_id", "order_index", name="uq_scenario_step_order"),
        CheckConstraint("order_index >= 1", name="chk_order_index_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"))
    order_index: Mapped[int] = mapped_column(nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    scenario: Mapped["Scenario"] = relationship(back_populates="steps")

    def __str__(self) -> str:
        preview = self.message_text[:40] + "..." if len(self.message_text) > 40 else self.message_text
        return f"Шаг {self.order_index}: {preview}"


class ChatSession(Base):
    """Сессия диалога одного пользователя."""
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scenario_id: Mapped[int | None] = mapped_column(ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True)

    # Порядковый номер текущего шага (1-based). None — сценарий ещё не выбран.
    current_step_index: Mapped[int | None] = mapped_column(nullable=True)

    # Статусы:
    #   pending_scenario   — ждём выбора сценария
    #   in_progress        — задаём вопросы сценария
    #   pending_contact    — собираем контактные данные
    #   generating         — генерируем отчёт
    #   completed          — отчёт готов
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_scenario")

    # Контактные данные (собираются в конце)
    contact_name: Mapped[str | None] = mapped_column(String(200))
    contact_email: Mapped[str | None] = mapped_column(String(200))
    contact_phone: Mapped[str | None] = mapped_column(String(50))
    # Какое поле контакта собираем сейчас: name / email / phone
    pending_contact_field: Mapped[str | None] = mapped_column(String(20))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    scenario: Mapped["Scenario | None"] = relationship(back_populates="sessions")
    entries: Mapped[list["DialogEntry"]] = relationship(
        back_populates="session",
        order_by="DialogEntry.created_at",
        cascade="all, delete-orphan",
    )
    report: Mapped["Report | None"] = relationship(back_populates="session", uselist=False)


class DialogEntry(Base):
    """Одна пара вопрос/ответ в диалоге."""
    __tablename__ = "dialog_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    step_index: Mapped[int | None] = mapped_column(nullable=True)  # None для служебных сообщений
    bot_message: Mapped[str] = mapped_column(Text, nullable=False)
    user_answer: Mapped[str | None] = mapped_column(Text)  # None если ответа ещё нет
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["ChatSession"] = relationship(back_populates="entries")


class Report(Base):
    """Сгенерированный PDF-отчёт."""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), unique=True)
    pdf_path: Mapped[str] = mapped_column(String(500), nullable=False)
    llm_response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    sent_to_bitrix: Mapped[bool] = mapped_column(Boolean, default=False)
    bitrix_deal_id: Mapped[str | None] = mapped_column(String(100))

    session: Mapped["ChatSession"] = relationship(back_populates="report")


_DEFAULT_CLASSIFICATION_PROMPT = (
    "Определи тип ответа пользователя. Ответь ТОЛЬКО одним словом: TYPE1, TYPE2 или TYPE3.\n\n"
    "ТИП 1 — НЕОСМЫСЛЕННЫЙ: случайные символы/буквы, ответ совершенно не относится к вопросу, "
    "намеренное уклонение (например: «пропустить», «не хочу отвечать», «неважно»).\n"
    "ТИП 2 — НИЗКИЙ УРОВЕНЬ: пользователь не владеет темой вопроса. "
    "Признак — ответ очень короткий и лишён содержания. "
    "Примеры таких ответов (не исчерпывающий список): «не знаю», «сложно сказать», "
    "«всё плохо», «нормально», «никак», «не думали об этом».\n"
    "ТИП 3 — ОСМЫСЛЕННЫЙ: пользователь описывает реальную ситуацию в компании, "
    "ответ по смыслу относится к вопросу. Даже короткий, но содержательный ответ "
    "относится к этому типу (например: «CRM не используем», «всё в Excel», "
    "«менеджеры работают по-своему»).\n\n"
    "Вопрос: {question}\n"
    "Ответ: {answer}"
)

_DEFAULT_TYPE1_MESSAGE = (
    "Я не смог понять ваш ответ. Пожалуйста, ответьте на вопрос подробнее — "
    "это поможет сделать диагностику точной и полезной для вас.\n"
    "{question}"
)


_DEFAULT_NEXT_STEP_TEXT = (
    "Присоединяйтесь к Программе AI Booster — комплексному курсу по внедрению искусственного "
    "интеллекта в бизнес. За 6 недель вы получите практические инструменты, поддержку экспертов "
    "и готовые решения, адаптированные под задачи вашей компании.\n\n"
    "Узнайте подробнее и запишитесь на сайте: ai-booster.ru"
)

_DEFAULT_GLOBAL_SYSTEM_PROMPT = """Ты — эксперт по цифровой трансформации от компании AI Booster.
Проведи диагностику компании на основе диалога и сформируй структурированный отчёт.

Используй СТРОГО следующую структуру — четыре раздела с заголовками первого уровня:

# ОСНОВНАЯ ПРОБЛЕМА
Краткое описание ключевой проблемы (2-3 предложения). Без воды.

# УРОВЕНЬ ЦИФРОВОЙ ЗРЕЛОСТИ
Напиши одно предложение с общим уровнем зрелости компании (низкий / средний / высокий).
Затем СТРОГО выведи четыре строки в точном формате (замени N на целое число от 1 до 5):
Процессы: N/5
Данные: N/5
Технологии: N/5
Персонал: N/5

# ТЕКУЩЕЕ СОСТОЯНИЕ
Анализ ситуации: что происходит в компании, корневые причины проблем (3-5 предложений).

# РЕКОМЕНДАЦИИ
- Рекомендация 1
- Рекомендация 2
- Рекомендация 3
Конкретные первые шаги (3-5 пунктов).

Пиши деловым, понятным языком. Без воды и общих фраз."""


class GlobalSettings(Base):
    """Глобальные настройки системы (синглтон, id=1)."""
    __tablename__ = "global_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    default_system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default=_DEFAULT_GLOBAL_SYSTEM_PROMPT)
    next_step_text: Mapped[str] = mapped_column(Text, nullable=False, default=_DEFAULT_NEXT_STEP_TEXT)

    def __str__(self) -> str:
        return "Глобальные настройки"


class ValidationSettings(Base):
    """Настройки валидации ответов пользователя (синглтон, id=1)."""
    __tablename__ = "validation_settings"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Главный включатель валидации
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ТИП 1 — неосмысленный ответ: повторяем вопрос
    type1_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    type1_message: Mapped[str] = mapped_column(Text, nullable=False, default=_DEFAULT_TYPE1_MESSAGE)

    # ТИП 2 — низкий уровень: отмечаем ответ в диалоге для LLM
    type2_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    type2_answer_tag: Mapped[str] = mapped_column(
        String(200), nullable=False,
        default="[Уровень ответа: низкий — пользователь не владеет темой]",
    )

    # Промт для классификации (с плейсхолдерами {question} и {answer})
    classification_prompt: Mapped[str] = mapped_column(Text, nullable=False, default=_DEFAULT_CLASSIFICATION_PROMPT)

    def __str__(self) -> str:
        return "Настройки валидации"