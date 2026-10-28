"""add credit score to customers

Revision ID: a3c91d7e5b42
Revises: 81527e5c5d66
Create Date: 2026-10-28 12:00:00.000000

"""

from collections.abc import Sequence
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c91d7e5b42"
down_revision: str | Sequence[str] | None = "81527e5c5d66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _score(monthly_income: Decimal, age: int, existing_emi: Decimal) -> int:
    """A frozen copy of services.credit_score.compute_credit_score as it was when
    this migration was written, so later formula changes never alter this migration."""
    income_points = min(Decimal(200), monthly_income / Decimal(100000) * 200)
    burden = min(existing_emi / monthly_income, Decimal(1))
    emi_points = 250 * (1 - burden)
    age_points = 100 if 25 <= age <= 55 else 60 if 21 <= age <= 60 else 0
    score = 300 + income_points + emi_points + age_points
    score = int(score.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return max(300, min(850, score))


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("customers", sa.Column("credit_score", sa.Integer(), nullable=True))

    bind = op.get_bind()
    today = datetime.now().astimezone().date()
    rows = bind.execute(
        sa.text(
            "SELECT c.id, c.monthly_income, c.date_of_birth, "
            "COALESCE(SUM(l.emi) FILTER (WHERE l.status = 'APPROVED'), 0) "
            "FROM customers c LEFT JOIN loans l ON l.customer_id = c.id "
            "GROUP BY c.id, c.monthly_income, c.date_of_birth"
        )
    ).all()
    for customer_id, income, dob, emi in rows:
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        bind.execute(
            sa.text("UPDATE customers SET credit_score = :score WHERE id = :id"),
            {"score": _score(Decimal(income), age, Decimal(emi)), "id": customer_id},
        )

    op.alter_column("customers", "credit_score", nullable=False)
    op.create_check_constraint(
        "check_credit_score",
        "customers",
        "credit_score >= 300 AND credit_score <= 850",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("check_credit_score", "customers", type_="check")
    op.drop_column("customers", "credit_score")
