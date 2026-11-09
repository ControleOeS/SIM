"""Perfis renomeados e refeitos: usuário, planejador, faturamento, controle e controle geral.

Contas existentes (decisão do responsável em 2026-10-27): administrador geral vira Controle Geral;
controlador geral e administrador de acessos viram Controle; usuário de obra continua.

Revision ID: 0009
Revises: 0008
"""
from __future__ import annotations

from alembic import op


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_ANTIGOS = "'usuario', 'administrador_acessos', 'controlador_geral', 'administrador_geral'"
_NOVOS = "'usuario', 'planejador', 'faturamento', 'controle', 'controle_geral'"
_TODOS = (
    "'usuario', 'administrador_acessos', 'controlador_geral', 'administrador_geral', "
    "'planejador', 'faturamento', 'controle', 'controle_geral'"
)
_PARA_NOVOS = (
    ("administrador_geral", "controle_geral"),
    ("controlador_geral", "controle"),
    ("administrador_acessos", "controle"),
)
# Na volta: controle geral mantém tudo; controle vira controlador geral; planejador vira controlador
# geral (vê todas as obras); faturamento vira usuário de obra sem centros (precisa ser revisto).
_PARA_ANTIGOS = (
    ("controle_geral", "administrador_geral"),
    ("controle", "controlador_geral"),
    ("planejador", "controlador_geral"),
    ("faturamento", "usuario"),
)


def _trocar(perfis: str) -> None:
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_usuarios_perfil_valido"), type_="check")
        batch_op.create_check_constraint(op.f("ck_usuarios_perfil_valido"), f"perfil IN ({perfis})")
    with op.batch_alter_table("solicitacoes_acesso", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("ck_solicitacoes_acesso_perfil_valido"), type_="check")
        batch_op.create_check_constraint(
            op.f("ck_solicitacoes_acesso_perfil_valido"), f"perfil_solicitado IN ({perfis})"
        )


def _converter(pares) -> None:
    for antigo, novo in pares:
        # versao_sessao + 1: quem estiver logado entra de novo já com o perfil novo.
        op.execute(
            f"UPDATE usuarios SET perfil = '{novo}', versao_sessao = versao_sessao + 1 WHERE perfil = '{antigo}'"
        )
        op.execute(f"UPDATE solicitacoes_acesso SET perfil_solicitado = '{novo}' WHERE perfil_solicitado = '{antigo}'")


def upgrade() -> None:
    _trocar(_TODOS)
    _converter(_PARA_NOVOS)
    _trocar(_NOVOS)


def downgrade() -> None:
    _trocar(_TODOS)
    _converter(_PARA_ANTIGOS)
    _trocar(_ANTIGOS)
