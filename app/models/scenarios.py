from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Text, UniqueConstraint, CheckConstraint, BigInteger, DateTime

from db.base import Base

from datetime import datetime



class Scenarios(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    steps: Mapped[list["ScenariosFlow"]] = relationship(
        back_populates="scenario",
        order_by="ScenariosFlow.order_index",
        cascade="all, delete-orphan",
    )
    def __str__(self):
        return f"{self.name}"

class ScenariosFlow(Base):
    __tablename__ = "scenarios_flow"
    __table_args__ = (
        UniqueConstraint("scenario_id", "order_index", name="uq_scenario_step"),
        CheckConstraint("order_index >= 1", name="check_order_index_min_1"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"))
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(nullable=False)
    scenario: Mapped["Scenarios"] = relationship(back_populates="steps")

    def __str__(self):
        short_text = (self.message_text[:30] + '..') if len(self.message_text) > 30 else self.message_text
        return f"Шаг {self.order_index}: {short_text}"


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sender: Mapped[str] = mapped_column(nullable=False)  # "bot" или "user"
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Опционально: привязка к сценарию, чтобы знать, в рамках чего был чат
    scenario_id: Mapped[int] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=True)


