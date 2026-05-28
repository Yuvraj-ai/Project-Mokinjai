"""add is_superuser to users

Revision ID: 8b8151205831
Revises: 65d6f9f49fdc
Create Date: 2026-05-29 01:19:07.027941

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b8151205831'
down_revision: Union[str, None] = '65d6f9f49fdc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('is_superuser', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'is_superuser')
