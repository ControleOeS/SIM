"""Perfil administrador_geral: controlador geral que também administra acessos.

Revision ID: 0005
Revises: 0004
"""
from __future__ import annotations

from alembic import op


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_ANTIGOS = "'usuario', 'administrador_acessos', 'controlador_geral'"
_NOVOS = "'usuario', 'administrador_acessos', 'controlador_geral', 'administrador_geral'"


def _trocar(perfis: str) -> None:
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_usuarios_perfil_valido"), type_="check")
        batch_op.create_check_constraint(op.f("ck_usuarios_perfil_valido"), f"perfil IN ({perfis})")
    with op.batch_alter_table("solicitacoes_acesso", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_solicitacoes_acesso_perfil_valido"), type_="check")
        batch_op.create_check_constraint(
            op.f("ck_solicitacoes_acesso_perfil_valido"), f"perfil_solicitado IN ({perfis})"
        )


def upgrade() -> None:
    _trocar(_NOVOS)


def downgrade() -> None:
    # Vira administrador de acessos para o sistema não ficar sem quem gerencie contas
    # (sem administrador ativo o login fica bloqueado); o acesso às obras precisa ser revisto.
    op.execute("UPDATE usuarios SET perfil = 'administrador_acessos' WHERE perfil = 'administrador_geral'")
    op.execute(
        "UPDATE solicitacoes_acesso SET perfil_solicitado = 'administrador_acessos' "
        "WHERE perfil_solicitado = 'administrador_geral'"
    )
    _trocar(_ANTIGOS)
