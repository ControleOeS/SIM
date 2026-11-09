"""Valor previsto por centro de custo e mês (SUPERUS) e justificativa de variação no BM mensal.

Revision ID: 0012
Revises: 0011
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "superus_valores_previstos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("centro_custo_id", sa.Integer(), nullable=False),
        sa.Column("ano", sa.String(length=20), nullable=False),
        sa.Column("mes_referencia", sa.String(length=40), nullable=False),
        sa.Column("valor", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["centro_custo_id"], ["superus_centros_custo.id"],
            name=op.f("fk_superus_valores_previstos_centro_custo_id_superus_centros_custo"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_superus_valores_previstos")),
        sa.UniqueConstraint("centro_custo_id", "ano", "mes_referencia", name="uq_valor_previsto_cc_mes"),
    )
    op.create_index(
        op.f("ix_superus_valores_previstos_centro_custo_id"), "superus_valores_previstos", ["centro_custo_id"]
    )
    with op.batch_alter_table("superus_bms_mensais", schema=None) as batch_op:
        batch_op.add_column(sa.Column("valor_previsto", sa.Numeric(precision=15, scale=2), nullable=True))
        batch_op.add_column(sa.Column("justificativa_variacao", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("superus_bms_mensais", schema=None) as batch_op:
        batch_op.drop_column("justificativa_variacao")
        batch_op.drop_column("valor_previsto")
    op.drop_index(op.f("ix_superus_valores_previstos_centro_custo_id"), table_name="superus_valores_previstos")
    op.drop_table("superus_valores_previstos")
