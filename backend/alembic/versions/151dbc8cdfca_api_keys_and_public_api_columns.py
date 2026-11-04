"""api keys and public api columns

Revision ID: 151dbc8cdfca
Revises: f595809bdfee
Create Date: 2026-11-05 02:15:06.446122

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '151dbc8cdfca'
down_revision: Union[str, None] = 'f595809bdfee'
branch_labels: Union[str, Sequence[str]] = None
depends_on: Union[str, Sequence[str]] = None


def upgrade() -> None:
    op.add_column('api_keys', sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('api_keys', sa.Column('disabled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('api_keys', sa.Column('credit_limit_usd', sa.Numeric(12, 2), nullable=True))
    op.add_column('api_keys', sa.Column('credit_reset_period', sa.String(10), nullable=True))
    op.add_column('api_keys', sa.Column('spend_window_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('api_keys', sa.Column('description', sa.Text(), nullable=True))
    op.create_index('ix_api_keys_workspace_id', 'api_keys', ['workspace_id'])

    op.add_column(
        'executions',
        sa.Column('api_key_id', sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        'fk_executions_api_key_id', 'executions', 'api_keys', ['api_key_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_executions_api_key_id', 'executions', ['api_key_id'])

    op.add_column(
        'chat_sessions',
        sa.Column('api_key_id', sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        'fk_chat_sessions_api_key_id', 'chat_sessions', 'api_keys', ['api_key_id'], ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_chat_sessions_api_key_id', 'chat_sessions', ['api_key_id'])


def downgrade() -> None:
    op.drop_index('ix_chat_sessions_api_key_id', table_name='chat_sessions')
    op.drop_constraint('fk_chat_sessions_api_key_id', 'chat_sessions', type_='foreignkey')
    op.drop_column('chat_sessions', 'api_key_id')

    op.drop_index('ix_executions_api_key_id', table_name='executions')
    op.drop_constraint('fk_executions_api_key_id', 'executions', type_='foreignkey')
    op.drop_column('executions', 'api_key_id')

    op.drop_index('ix_api_keys_workspace_id', table_name='api_keys')
    op.drop_column('api_keys', 'description')
    op.drop_column('api_keys', 'spend_window_started_at')
    op.drop_column('api_keys', 'credit_reset_period')
    op.drop_column('api_keys', 'credit_limit_usd')
    op.drop_column('api_keys', 'disabled_at')
    op.drop_column('api_keys', 'revoked_at')
