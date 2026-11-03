"""add playground chat tables

Revision ID: f595809bdfee
Revises: d8f4a1b6c2e9
Create Date: 2026-11-03 22:43:31.681322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'f595809bdfee'
down_revision: Union[str, None] = 'd8f4a1b6c2e9'
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS chat_messages_seq_seq")
    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column(
            'workspace_id',
            sa.String(36),
            sa.ForeignKey('workspaces.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'agent_id',
            sa.String(36),
            sa.ForeignKey('agents.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('title', sa.String(255), nullable=False, server_default='New session'),
        sa.Column(
            'created_by',
            sa.String(36),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        'ix_chat_sessions_agent_id', 'chat_sessions', ['agent_id']
    )
    op.create_index(
        'ix_chat_sessions_workspace_updated', 'chat_sessions', ['workspace_id', 'updated_at']
    )

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column(
            'session_id',
            sa.String(36),
            sa.ForeignKey('chat_sessions.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column(
            'seq',
            sa.BigInteger(),
            sa.Sequence('chat_messages_seq_seq'),
            nullable=False,
            unique=True,
        ),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('activity', JSONB(), nullable=True),
        sa.Column('structured', JSONB(), nullable=True),
        sa.Column('status', sa.String(16), nullable=True),
        sa.Column('usage', JSONB(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(12, 8), nullable=True),
        sa.Column(
            'execution_id',
            sa.String(36),
            sa.ForeignKey('executions.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])
    op.create_index(
        'ix_chat_messages_session_created', 'chat_messages', ['session_id', 'created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_chat_messages_session_created', table_name='chat_messages')
    op.drop_index('ix_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.execute("DROP SEQUENCE IF EXISTS chat_messages_seq_seq")
    op.drop_index('ix_chat_sessions_workspace_updated', table_name='chat_sessions')
    op.drop_index('ix_chat_sessions_agent_id', table_name='chat_sessions')
    op.drop_table('chat_sessions')
