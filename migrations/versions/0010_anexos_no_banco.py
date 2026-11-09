"""Conteúdo de anexos no banco (SIM_ANEXOS_BACKEND=banco), para hospedagem sem disco persistente.

Revision ID: 0010
Revises: 0009
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anexos_conteudo",
        sa.Column("caminho_relativo", sa.String(length=500), nullable=False),
        sa.Column("conteudo", sa.LargeBinary(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("caminho_relativo", name=op.f("pk_anexos_conteudo")),
    )


def downgrade() -> None:
    op.drop_table("anexos_conteudo")
