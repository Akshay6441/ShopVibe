"""Fraud flags on orders + support tickets

Revision ID: 002
Revises: 001
Create Date: 2026-08-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column("orders", sa.Column("is_fraud_flagged", sa.Boolean(), server_default=sa.false(),
                                      nullable=False))
    op.add_column("orders", sa.Column("fraud_reason", sa.String(500), nullable=True))

    ticketstatus = sa.Enum("open", "resolved", name="ticketstatus")
    if bind.dialect.name == "postgresql":
        ticketstatus.create(bind, checkfirst=True)

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status",
                  sa.Enum("open", "resolved", name="ticketstatus")
                  if bind.dialect.name == "postgresql"
                  else sa.String(20),
                  default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_support_tickets_id", "support_tickets", ["id"])
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_support_tickets_user_id", table_name="support_tickets")
    op.drop_index("ix_support_tickets_id", table_name="support_tickets")
    op.drop_table("support_tickets")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum("open", "resolved", name="ticketstatus").drop(bind, checkfirst=True)

    op.drop_column("orders", "fraud_reason")
    op.drop_column("orders", "is_fraud_flagged")
