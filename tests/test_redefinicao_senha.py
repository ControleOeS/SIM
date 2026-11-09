"""Redefinição de senha pelo usuário com código enviado por e-mail."""
from __future__ import annotations

import re
from datetime import timedelta
from email import message_from_bytes, policy
from pathlib import Path

import pytest
from sqlalchemy import select, update

from sim import database, redefinicao_senha
from sim.auth import PERFIL_USUARIO, autenticar
from sim.errors import ValidationError
from sim.models import AuditoriaAcesso, CodigoRedefinicaoSenha, DominioPermitido, Usuario, utcnow
from tests.test_access import _usuario

SENHA_ANTIGA = "Senha-forte-de-teste-123"


@pytest.fixture
def com_email(ambiente, monkeypatch):
    monkeypatch.setenv("SIM_EMAIL_MODO", "arquivo")
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        session.add(_usuario("pessoa@empresa.test", PERFIL_USUARIO, SENHA_ANTIGA))
    return Path(ambiente.data_dir) / "emails"


def _emails(pasta: Path) -> list[str]:
    if not pasta.exists():
        return []
    return [message_from_bytes(p.read_bytes(), policy=policy.default).get_content() for p in sorted(pasta.glob("*.eml"))]


def _codigo(pasta: Path) -> str:
    return re.search(r"\b(\d{6})\b", _emails(pasta)[-1]).group(1)


def _liberar_novo_pedido():
    """Simula a passagem do intervalo mínimo entre pedidos."""
    with database.session_scope() as session:
        session.execute(
            update(CodigoRedefinicaoSenha).values(criado_em=utcnow() - timedelta(minutes=2))
        )


def test_fluxo_completo_troca_senha_e_invalida_codigo(com_email):
    redefinicao_senha.solicitar_codigo("Pessoa@Empresa.test")
    [corpo] = _emails(com_email)
    assert "15 minutos" in corpo
    codigo = _codigo(com_email)
    with database.session_scope() as session:
        assert codigo not in session.scalar(select(CodigoRedefinicaoSenha.codigo_hash))
        versao_antes = session.scalar(select(Usuario.versao_sessao))

    redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", codigo, "novasenha", "novasenha")

    assert autenticar("pessoa@empresa.test", SENHA_ANTIGA) is None
    login = autenticar("pessoa@empresa.test", "novasenha")
    assert login is not None and login[1] == versao_antes + 1
    with pytest.raises(ValidationError):
        redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", codigo, "outrasenha", "outrasenha")
    with database.session_scope() as session:
        assert session.scalar(select(AuditoriaAcesso.acao)) == "redefinir_senha_por_email"


def test_email_sem_conta_nao_envia_e_nao_revela(com_email):
    redefinicao_senha.solicitar_codigo("ninguem@empresa.test")
    assert _emails(com_email) == []
    with pytest.raises(ValidationError) as erro:
        redefinicao_senha.redefinir_com_codigo("ninguem@empresa.test", "123456", "novasenha", "novasenha")
    assert "Código inválido" in erro.value.errors["codigo"]


def test_cinco_erros_invalidam_o_codigo(com_email):
    redefinicao_senha.solicitar_codigo("pessoa@empresa.test")
    codigo = _codigo(com_email)
    errado = "000000" if codigo != "000000" else "111111"
    for _ in range(redefinicao_senha.MAX_TENTATIVAS):
        with pytest.raises(ValidationError):
            redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", errado, "novasenha", "novasenha")
    with pytest.raises(ValidationError):
        redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", codigo, "novasenha", "novasenha")
    assert autenticar("pessoa@empresa.test", SENHA_ANTIGA) is not None


def test_codigo_expirado_e_recusado(com_email):
    redefinicao_senha.solicitar_codigo("pessoa@empresa.test")
    codigo = _codigo(com_email)
    with database.session_scope() as session:
        session.execute(update(CodigoRedefinicaoSenha).values(expira_em=utcnow() - timedelta(seconds=1)))
    with pytest.raises(ValidationError):
        redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", codigo, "novasenha", "novasenha")


def test_novo_codigo_invalida_o_anterior_e_respeita_intervalo(com_email):
    redefinicao_senha.solicitar_codigo("pessoa@empresa.test")
    primeiro = _codigo(com_email)
    redefinicao_senha.solicitar_codigo("pessoa@empresa.test")  # antes de 60 s: ignorado
    assert len(_emails(com_email)) == 1

    _liberar_novo_pedido()
    redefinicao_senha.solicitar_codigo("pessoa@empresa.test")
    segundo = _codigo(com_email)
    assert len(_emails(com_email)) == 2
    if primeiro != segundo:
        with pytest.raises(ValidationError):
            redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", primeiro, "novasenha", "novasenha")
    redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", segundo, "novasenha", "novasenha")


def test_redefinicao_desbloqueia_conta_e_valida_senha(com_email):
    for _ in range(5):
        autenticar("pessoa@empresa.test", "errada")
    assert autenticar("pessoa@empresa.test", SENHA_ANTIGA) is None  # bloqueada

    redefinicao_senha.solicitar_codigo("pessoa@empresa.test")
    codigo = _codigo(com_email)
    with pytest.raises(ValidationError) as erro:
        redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", codigo, "curta", "curta")
    assert "senha" in erro.value.errors
    redefinicao_senha.redefinir_com_codigo("pessoa@empresa.test", codigo, "novasenha", "novasenha")
    assert autenticar("pessoa@empresa.test", "novasenha") is not None


def test_sem_envio_configurado_nada_e_gerado(ambiente, monkeypatch):
    monkeypatch.setenv("SIM_EMAIL_MODO", "desativado")
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        session.add(_usuario("pessoa@empresa.test", PERFIL_USUARIO))
    assert not redefinicao_senha.disponivel()
    redefinicao_senha.solicitar_codigo("pessoa@empresa.test")
    with database.session_scope() as session:
        assert session.scalar(select(CodigoRedefinicaoSenha.id)) is None
