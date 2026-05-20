"""add_chat_messages_to_global_settings

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEFAULT_WELCOME_MESSAGE = (
    "Здравствуйте! Я AI-диагност от AI Booster. "
    "Я помогу вам структурировать ключевую бизнес-проблему и предложу первые шаги для её решения. "
    "Выберите проблему из ниже перечисленного списка:"
)

_DEFAULT_REPORT_READY_MESSAGE = (
    "Отчёт готов! Вы можете скачать его по ссылке ниже. "
    "Спасибо за прохождение диагностики!"
)


def upgrade() -> None:
    op.add_column(
        "global_settings",
        sa.Column("welcome_message", sa.Text(), nullable=False, server_default=_DEFAULT_WELCOME_MESSAGE),
    )
    op.add_column(
        "global_settings",
        sa.Column("report_ready_message", sa.Text(), nullable=False, server_default=_DEFAULT_REPORT_READY_MESSAGE),
    )
    op.execute(
        sa.text(
            "UPDATE global_settings SET welcome_message = :wm, report_ready_message = :rrm WHERE id = 1"
        ).bindparams(wm=_DEFAULT_WELCOME_MESSAGE, rrm=_DEFAULT_REPORT_READY_MESSAGE)
    )


def downgrade() -> None:
    op.drop_column("global_settings", "report_ready_message")
    op.drop_column("global_settings", "welcome_message")