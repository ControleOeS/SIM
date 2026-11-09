"""Uma resposta de BM mensal SUPERUS por centro de custo e mês (só BMs do SIM novo; o histórico tem repetidos).

Revision ID: 0013
Revises: 0012
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_superus_bm_mensal_mes", "superus_bms_mensais", ["centro_custo_id", "ano", "mes_referencia"], unique=True,
        sqlite_where=sa.text("id_legado IS NULL"), postgresql_where=sa.text("id_legado IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_superus_bm_mensal_mes", table_name="superus_bms_mensais")
