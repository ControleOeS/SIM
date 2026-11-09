"""Centro de custo ativo/inativo e solicitações de encerramento.

Revision ID: 0007
Revises: 0006
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for tabela in ("asap_centros_custo", "superus_centros_custo"):
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.add_column(sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False))

    op.create_table(
        "encerramentos_cc",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("asap_cc_id", sa.Integer(), nullable=True),
        sa.Column("superus_cc_id", sa.Integer(), nullable=True),
        sa.Column("acao", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("justificativa", sa.Text(), nullable=True),
        sa.Column("parecer", sa.Text(), nullable=True),
        sa.Column("solicitante_id", sa.Integer(), nullable=True),
        sa.Column("decidido_por_id", sa.Integer(), nullable=True),
        sa.Column("decidido_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(asap_cc_id IS NOT NULL AND superus_cc_id IS NULL)"
            " OR (asap_cc_id IS NULL AND superus_cc_id IS NOT NULL)",
            name=op.f("ck_encerramentos_cc_um_centro_custo"),
        ),
        sa.CheckConstraint("acao IN ('encerrar', 'reativar')", name=op.f("ck_encerramentos_cc_acao_valida")),
        sa.CheckConstraint(
            "status IN ('pendente', 'aprovada', 'recusada')", name=op.f("ck_encerramentos_cc_status_valido")
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"], ["empresas.id"], name=op.f("fk_encerramentos_cc_empresa_id_empresas"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["asap_cc_id"],
            ["asap_centros_custo.id"],
            name=op.f("fk_encerramentos_cc_asap_cc_id_asap_centros_custo"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["superus_cc_id"],
            ["superus_centros_custo.id"],
            name=op.f("fk_encerramentos_cc_superus_cc_id_superus_centros_custo"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["solicitante_id"],
            ["usuarios.id"],
            name=op.f("fk_encerramentos_cc_solicitante_id_usuarios"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decidido_por_id"],
            ["usuarios.id"],
            name=op.f("fk_encerramentos_cc_decidido_por_id_usuarios"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_encerramentos_cc")),
    )
    with op.batch_alter_table("encerramentos_cc", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_encerramentos_cc_asap_cc_id"), ["asap_cc_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_encerramentos_cc_superus_cc_id"), ["superus_cc_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_encerramentos_cc_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("encerramentos_cc", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_encerramentos_cc_status"))
        batch_op.drop_index(batch_op.f("ix_encerramentos_cc_superus_cc_id"))
        batch_op.drop_index(batch_op.f("ix_encerramentos_cc_asap_cc_id"))
    op.drop_table("encerramentos_cc")
    for tabela in ("superus_centros_custo", "asap_centros_custo"):
        with op.batch_alter_table(tabela, schema=None) as batch_op:
            batch_op.drop_column("ativo")
