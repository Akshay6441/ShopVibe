"""Salesforce sync linkage columns

Revision ID: 003
Revises: 002
Create Date: 2026-08-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("salesforce_id", sa.String(18), nullable=True))
    op.create_index("ix_orders_salesforce_id", "orders", ["salesforce_id"])

    op.add_column("users", sa.Column("sf_contact_id", sa.String(18), nullable=True))
    op.add_column("users", sa.Column("sf_account_id", sa.String(18), nullable=True))
    op.create_index("ix_users_sf_contact_id", "users", ["sf_contact_id"])


def downgrade() -> None:
    op.drop_index("ix_users_sf_contact_id", table_name="users")
    op.drop_column("users", "sf_account_id")
    op.drop_column("users", "sf_contact_id")

    op.drop_index("ix_orders_salesforce_id", table_name="orders")
    op.drop_column("orders", "salesforce_id")
