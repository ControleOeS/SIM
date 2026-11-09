"""Solicitações de acesso feitas na tela de login e aprovadas por administrador.

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solicitacoes_acesso",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalizado", sa.String(length=320), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=True),
        sa.Column("perfil_solicitado", sa.String(length=30), nullable=False),
        sa.Column("centro_custo_informado", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("parecer", sa.Text(), nullable=True),
        sa.Column("decidido_por_id", sa.Integer(), nullable=True),
        sa.Column("decidido_em", sa.DateTime(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "perfil_solicitado IN ('usuario', 'administrador_acessos', 'controlador_geral')",
            name=op.f("ck_solicitacoes_acesso_perfil_valido"),
        ),
        sa.CheckConstraint(
            "status IN ('pendente', 'aprovada', 'recusada')",
            name=op.f("ck_solicitacoes_acesso_status_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["decidido_por_id"],
            ["usuarios.id"],
            name=op.f("fk_solicitacoes_acesso_decidido_por_id_usuarios"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_solicitacoes_acesso_usuario_id_usuarios"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_solicitacoes_acesso")),
    )
    with op.batch_alter_table("solicitacoes_acesso", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_solicitacoes_acesso_email_normalizado"), ["email_normalizado"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_solicitacoes_acesso_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("solicitacoes_acesso", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_solicitacoes_acesso_status"))
        batch_op.drop_index(batch_op.f("ix_solicitacoes_acesso_email_normalizado"))
    op.drop_table("solicitacoes_acesso")
