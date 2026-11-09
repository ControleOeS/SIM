"""Edição simultânea: coluna de versão nos registros editáveis e pedidos pendentes únicos.

Revision ID: 0008
Revises: 0007
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

TABELAS_VERSIONADAS = (
    "asap_centros_custo",
    "asap_bms",
    "superus_centros_custo",
    "superus_bms_mensais",
    "superus_bms_semanais",
)
PENDENTE = sa.text("status = 'pendente'")


def upgrade() -> None:
    for tabela in TABELAS_VERSIONADAS:
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column("versao", sa.Integer(), server_default=sa.text("1"), nullable=False))

    op.create_index(
        "uq_solicitacoes_acesso_pendente", "solicitacoes_acesso", ["email_normalizado"], unique=True,
        sqlite_where=PENDENTE, postgresql_where=PENDENTE,
    )
    op.create_index(
        "uq_encerramentos_cc_asap_pendente", "encerramentos_cc", ["asap_cc_id"], unique=True,
        sqlite_where=PENDENTE, postgresql_where=PENDENTE,
    )
    op.create_index(
        "uq_encerramentos_cc_superus_pendente", "encerramentos_cc", ["superus_cc_id"], unique=True,
        sqlite_where=PENDENTE, postgresql_where=PENDENTE,
    )


def downgrade() -> None:
    op.drop_index("uq_encerramentos_cc_superus_pendente", table_name="encerramentos_cc")
    op.drop_index("uq_encerramentos_cc_asap_pendente", table_name="encerramentos_cc")
    op.drop_index("uq_solicitacoes_acesso_pendente", table_name="solicitacoes_acesso")
    for tabela in reversed(TABELAS_VERSIONADAS):
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_column("versao")
