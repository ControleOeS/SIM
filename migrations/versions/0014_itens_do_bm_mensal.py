"""BMs que compõem a resposta mensal SUPERUS (o gestor lança BM por BM; o SIM soma).

Revision ID: 0014
Revises: 0013
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "superus_bm_mensal_itens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bm_id", sa.Integer(), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        sa.Column("valor_bm", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("valor_aprovado", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.ForeignKeyConstraint(
            ["bm_id"], ["superus_bms_mensais.id"],
            name=op.f("fk_superus_bm_mensal_itens_bm_id_superus_bms_mensais"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_superus_bm_mensal_itens")),
    )
    op.create_index(op.f("ix_superus_bm_mensal_itens_bm_id"), "superus_bm_mensal_itens", ["bm_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_superus_bm_mensal_itens_bm_id"), table_name="superus_bm_mensal_itens")
    op.drop_table("superus_bm_mensal_itens")
