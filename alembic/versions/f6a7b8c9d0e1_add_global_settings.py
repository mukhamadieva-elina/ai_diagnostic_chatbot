"""add_global_settings

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-04-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
Оцени каждое направление по шкале 1-5 в формате "Направление: N/5":
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


def upgrade() -> None:
    op.create_table(
        "global_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("default_system_prompt", sa.Text(), nullable=False),
        sa.Column("next_step_text", sa.Text(), nullable=False),
    )
    op.execute(
        sa.text(
            "INSERT INTO global_settings (id, default_system_prompt, next_step_text) "
            "VALUES (1, :prompt, :next_step)"
        ).bindparams(
            prompt=_DEFAULT_GLOBAL_SYSTEM_PROMPT,
            next_step=_DEFAULT_NEXT_STEP_TEXT,
        )
    )


def downgrade() -> None:
    op.drop_table("global_settings")
