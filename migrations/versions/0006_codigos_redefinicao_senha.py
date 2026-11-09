"""Códigos de redefinição de senha enviados por e-mail.

Revision ID: 0006
Revises: 0005
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "codigos_redefinicao_senha",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("codigo_hash", sa.String(length=255), nullable=False),
        sa.Column("expira_em", sa.DateTime(), nullable=False),
        sa.Column("tentativas", sa.Integer(), nullable=False),
        sa.Column("usado_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_codigos_redefinicao_senha_usuario_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_codigos_redefinicao_senha")),
    )
    with op.batch_alter_table("codigos_redefinicao_senha", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_codigos_redefinicao_senha_usuario_id"), ["usuario_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("codigos_redefinicao_senha", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_codigos_redefinicao_senha_usuario_id"))
    op.drop_table("codigos_redefinicao_senha")
