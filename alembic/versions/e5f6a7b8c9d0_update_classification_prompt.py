"""update_classification_prompt

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-27 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_PROMPT = (
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


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE validation_settings SET classification_prompt = :p WHERE id = 1").bindparams(p=_NEW_PROMPT)
    )


def downgrade() -> None:
    pass
