"""add_validation_settings

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-27 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
    "это поможет сделать диагностику точной и полезной для вас.\n\n"
    "{question}"
)


def upgrade() -> None:
    op.create_table(
        "validation_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("type1_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("type1_message", sa.Text(), nullable=False),
        sa.Column("type2_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("type2_answer_tag", sa.String(200), nullable=False),
        sa.Column("classification_prompt", sa.Text(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO validation_settings "
            "(id, enabled, type1_enabled, type1_message, type2_enabled, type2_answer_tag, classification_prompt) "
            "VALUES (1, true, true, :t1msg, true, :t2tag, :prompt)"
        ).bindparams(
            t1msg=_DEFAULT_TYPE1_MESSAGE,
            t2tag="[Уровень ответа: низкий — пользователь не владеет темой]",
            prompt=_DEFAULT_CLASSIFICATION_PROMPT,
        )
    )


def downgrade() -> None:
    op.drop_table("validation_settings")
