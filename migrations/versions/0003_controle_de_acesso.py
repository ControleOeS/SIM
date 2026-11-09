"""Contas locais e concessões de acesso por centro de custo.

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_normalizado", sa.String(length=320), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("perfil", sa.String(length=30), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("deve_trocar_senha", sa.Boolean(), nullable=False),
        sa.Column("tentativas_login", sa.Integer(), nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime(), nullable=True),
        sa.Column("versao_sessao", sa.Integer(), nullable=False),
        sa.Column("ultimo_login_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "perfil IN ('usuario', 'administrador_acessos', 'controlador_geral')",
            name=op.f("ck_usuarios_perfil_valido"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuarios")),
        sa.UniqueConstraint("email_normalizado", name=op.f("uq_usuarios_email_normalizado")),
    )
    op.create_table(
        "dominios_permitidos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dominio", sa.String(length=253), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dominios_permitidos")),
        sa.UniqueConstraint("dominio", name=op.f("uq_dominios_permitidos_dominio")),
    )
    op.create_table(
        "acessos_centros_custo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("asap_centro_custo_id", sa.Integer(), nullable=True),
        sa.Column("superus_centro_custo_id", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(asap_centro_custo_id IS NOT NULL AND superus_centro_custo_id IS NULL)"
            " OR (asap_centro_custo_id IS NULL AND superus_centro_custo_id IS NOT NULL)",
            name=op.f("ck_acessos_centros_custo_um_centro_custo"),
        ),
        sa.CheckConstraint("empresa_id > 0", name=op.f("ck_acessos_centros_custo_empresa_positiva")),
        sa.ForeignKeyConstraint(
            ["asap_centro_custo_id"],
            ["asap_centros_custo.id"],
            name=op.f("fk_acessos_centros_custo_asap_centro_custo_id_asap_centros_custo"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["empresa_id"],
            ["empresas.id"],
            name=op.f("fk_acessos_centros_custo_empresa_id_empresas"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superus_centro_custo_id"],
            ["superus_centros_custo.id"],
            name=op.f("fk_acessos_centros_custo_superus_centro_custo_id_superus_centros_custo"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_acessos_centros_custo_usuario_id_usuarios"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_acessos_centros_custo")),
        sa.UniqueConstraint(
            "usuario_id", "asap_centro_custo_id", name="uq_acesso_usuario_asap_cc"
        ),
        sa.UniqueConstraint(
            "usuario_id", "superus_centro_custo_id", name="uq_acesso_usuario_superus_cc"
        ),
    )
    op.create_index(
        op.f("ix_acessos_centros_custo_usuario_id"),
        "acessos_centros_custo",
        ["usuario_id"],
        unique=False,
    )
    op.create_table(
        "auditoria_acessos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ator_usuario_id", sa.Integer(), nullable=True),
        sa.Column("alvo_usuario_id", sa.Integer(), nullable=True),
        sa.Column("acao", sa.String(length=60), nullable=False),
        sa.Column("detalhes", sa.Text(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["alvo_usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_auditoria_acessos_alvo_usuario_id_usuarios"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["ator_usuario_id"],
            ["usuarios.id"],
            name=op.f("fk_auditoria_acessos_ator_usuario_id_usuarios"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auditoria_acessos")),
    )
    op.create_index(
        op.f("ix_auditoria_acessos_criado_em"),
        "auditoria_acessos",
        ["criado_em"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_auditoria_acessos_criado_em"), table_name="auditoria_acessos")
    op.drop_table("auditoria_acessos")
    op.drop_index(op.f("ix_acessos_centros_custo_usuario_id"), table_name="acessos_centros_custo")
    op.drop_table("acessos_centros_custo")
    op.drop_table("dominios_permitidos")
    op.drop_table("usuarios")
