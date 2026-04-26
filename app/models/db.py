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