"""v2_new_schema

Revision ID: a1b2c3d4e5f6
Revises: 841465b8fdb5
Create Date: 2026-04-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '841465b8fdb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Удаляем старые таблицы
    op.drop_table('chat_history')
    op.drop_table('scenarios_flow')
    op.drop_table('scenarios')

    # scenarios — обновлённая таблица
    op.create_table(
        'scenarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # scenario_steps
    op.create_table(
        'scenario_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scenario_id', 'order_index', name='uq_scenario_step_order'),
        sa.CheckConstraint('order_index >= 1', name='chk_order_index_positive'),
    )

    # chat_sessions
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=True),
        sa.Column('current_step_index', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending_scenario'),
        sa.Column('contact_name', sa.String(200), nullable=True),
        sa.Column('contact_email', sa.String(200), nullable=True),
        sa.Column('contact_phone', sa.String(50), nullable=True),
        sa.Column('pending_contact_field', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # dialog_entries
    op.create_table(
        'dialog_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=True),
        sa.Column('bot_message', sa.Text(), nullable=False),
        sa.Column('user_answer', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # reports
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('pdf_path', sa.String(500), nullable=False),
        sa.Column('llm_response', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('now()')),
        sa.Column('sent_to_bitrix', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('bitrix_deal_id', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
    )


def downgrade() -> None:
    op.drop_table('reports')
    op.drop_table('dialog_entries')
    op.drop_table('chat_sessions')
    op.drop_table('scenario_steps')
    op.drop_table('scenarios')

    # Восстанавливаем старые таблицы
    op.create_table(
        'scenarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_table(
        'scenarios_flow',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('scenario_id', sa.Integer(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'chat_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.BigInteger(), nullable=False),
        sa.Column('sender', sa.String(), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('scenario_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['scenario_id'], ['scenarios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
