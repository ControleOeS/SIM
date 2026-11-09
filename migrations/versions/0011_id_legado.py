"""ID SharePoint dos BMs importados do histórico do Power Apps (importação repetível sem duplicar).

Revision ID: 0011
Revises: 0010
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

TABELAS = ("superus_bms_mensais", "superus_bms_semanais")


def upgrade() -> None:
    for tabela in TABELAS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column("id_legado", sa.Integer(), nullable=True))
            batch_op.create_unique_constraint(op.f(f"uq_{tabela}_id_legado"), ["id_legado"])


def downgrade() -> None:
    for tabela in TABELAS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_constraint(op.f(f"uq_{tabela}_id_legado"), type_="unique")
            batch_op.drop_column("id_legado")
