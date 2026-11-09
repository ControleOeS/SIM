"""Cadastra as empresas da holding (dado estrutural, não é dado de teste).

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

empresas = sa.table(
    "empresas",
    sa.column("codigo", sa.String),
    sa.column("nome", sa.String),
)


def upgrade() -> None:
    op.bulk_insert(
        empresas,
        [
            {"codigo": "ASAP", "nome": "ASAP"},
            {"codigo": "SUPERUS", "nome": "SUPERUS ENGENHARIA"},
        ],
    )


def downgrade() -> None:
    op.execute(empresas.delete().where(empresas.c.codigo.in_(["ASAP", "SUPERUS"])))
