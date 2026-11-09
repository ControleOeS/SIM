"""Solicitação de acesso pela tela de login e decisão pelo administrador/aprovador."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from sim import access_admin, database
from sim.auth import (
    PERFIL_CONTROLE_GERAL,
    PERFIL_CONTROLE,
    PERFIL_USUARIO,
    Principal,
    autenticar,
    carregar_principal,
    usando_principal,
)
from sim.errors import AuthorizationError, ValidationError
from sim.models import DominioPermitido, SolicitacaoAcesso, Usuario
from sim.services import asap
from tests.test_access import _usuario
from tests.test_asap import CC as CC_ASAP


def _admin() -> Principal:
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="oesgestao.test", ativo=True))
        session.add(DominioPermitido(dominio="parceiro.test", ativo=True))
        admin = _usuario("admin@oesgestao.test", PERFIL_CONTROLE_GERAL)
        session.add(admin)
        session.flush()
        admin_id = admin.id
    return Principal(admin_id, "admin@oesgestao.test", "Admin", PERFIL_CONTROLE_GERAL, 1, ())


def _solicitar(email: str = "obra@parceiro.test", perfil: str = PERFIL_USUARIO, centro: str = "CC 1234 - Obra Alfa"):
    with usando_principal(None):
        access_admin.solicitar_acesso("Pessoa da Obra", email, "senha123", "senha123", perfil, centro)


def _pendentes(admin: Principal) -> list[SolicitacaoAcesso]:
    with usando_principal(admin):
        return access_admin.listar_solicitacoes(access_admin.STATUS_PENDENTE)


def test_solicitacao_fica_pendente_e_nao_permite_login(ambiente):
    admin = _admin()
    _solicitar(centro="  CC 1234 - Obra Alfa (contrato 55/2026)  ")

    [pedido] = _pendentes(admin)
    assert pedido.centro_custo_informado == "CC 1234 - Obra Alfa (contrato 55/2026)"
    assert pedido.perfil_solicitado == PERFIL_USUARIO
    assert pedido.senha_hash and "senha123" not in pedido.senha_hash
    assert autenticar("obra@parceiro.test", "senha123") is None
    with usando_principal(admin):
        assert access_admin.contar_solicitacoes_pendentes() == 1


def test_validacao_do_formulario_publico(ambiente):
    with usando_principal(None):
        with pytest.raises(ValidationError) as erro:
            access_admin.solicitar_acesso("", "invalido", "curta", "outra", "gerente", "  ")
    assert set(erro.value.errors) == {"nome", "email", "senha", "confirmacao", "perfil", "centro_custo"}


def test_aprovacao_cria_conta_com_senha_escolhida_e_libera_centros(ambiente):
    cc_liberado = asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-ALFA"})
    cc_outro = asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-BETA"})
    admin = _admin()
    _solicitar()
    [pedido] = _pendentes(admin)

    with usando_principal(admin):
        usuario_id = access_admin.aprovar_solicitacao(
            pedido.id, PERFIL_USUARIO, [("ASAP", cc_liberado)], "CC informado confere com a Obra Alfa."
        )

    login = autenticar("obra@parceiro.test", "senha123")
    assert login is not None and login[0] == usuario_id
    principal = carregar_principal(*login)
    assert principal.escopos == (("ASAP", cc_liberado),)
    assert ("ASAP", cc_outro) not in principal.escopos
    with database.session_scope() as session:
        pedido = session.get(SolicitacaoAcesso, pedido.id)
        assert pedido.status == access_admin.STATUS_APROVADA
        assert pedido.senha_hash is None
        assert pedido.decidido_por_id == admin.id
        assert pedido.parecer == "CC informado confere com a Obra Alfa."
        assert not session.get(Usuario, usuario_id).deve_trocar_senha


def test_dominio_nao_autorizado_e_barrado_na_solicitacao(ambiente):
    admin = _admin()
    with pytest.raises(ValidationError) as erro:
        _solicitar("pedro@oesgestaaao.test")
    assert "oesgestaaao.test não está autorizado" in erro.value.errors["email"]
    with usando_principal(admin):  # domínio desativado também barra
        [dominio] = [d for d in access_admin.listar_dominios() if d.dominio == "parceiro.test"]
        access_admin.desativar_dominio(dominio.id)
    with pytest.raises(ValidationError):
        _solicitar()
    assert _pendentes(admin) == []


def test_aprovacao_nao_autoriza_dominio(ambiente):
    """Pedido antigo (ou domínio desativado depois do pedido): a aprovação é recusada."""
    admin = _admin()
    _solicitar()
    with usando_principal(admin):
        [dominio] = [d for d in access_admin.listar_dominios() if d.dominio == "parceiro.test"]
        access_admin.desativar_dominio(dominio.id)
        [pedido] = access_admin.listar_solicitacoes(access_admin.STATUS_PENDENTE)
        with pytest.raises(ValidationError) as erro:
            access_admin.aprovar_solicitacao(pedido.id, PERFIL_USUARIO, [], "")
        assert "não está autorizado" in erro.value.errors["email"]
        assert not access_admin.dominio_autorizado(pedido.email_normalizado)
        access_admin.recusar_solicitacao(pedido.id, "Domínio não autorizado.")
    assert autenticar("obra@parceiro.test", "senha123") is None


def test_aprovador_pode_mudar_classificacao_e_aprovar_novo_aprovador(ambiente):
    admin = _admin()
    _solicitar("gestor@oesgestao.test", PERFIL_CONTROLE)
    _solicitar("aprovador@oesgestao.test", PERFIL_CONTROLE_GERAL)
    gestor, aprovador = _pendentes(admin)

    with usando_principal(admin):
        access_admin.aprovar_solicitacao(gestor.id, PERFIL_USUARIO)
        novo_admin_id = access_admin.aprovar_solicitacao(aprovador.id, PERFIL_CONTROLE_GERAL)

    assert carregar_principal(*autenticar("gestor@oesgestao.test", "senha123")).perfil == PERFIL_USUARIO
    novo_admin = carregar_principal(*autenticar("aprovador@oesgestao.test", "senha123"))
    assert novo_admin.id == novo_admin_id and novo_admin.administrador_acessos

    _solicitar("terceiro@oesgestao.test")
    [pedido] = _pendentes(novo_admin)
    with usando_principal(novo_admin):
        access_admin.aprovar_solicitacao(pedido.id, PERFIL_USUARIO)
    assert autenticar("terceiro@oesgestao.test", "senha123") is not None


def test_recusa_exige_parecer_e_nao_cria_conta(ambiente):
    admin = _admin()
    _solicitar()
    [pedido] = _pendentes(admin)

    with usando_principal(admin):
        with pytest.raises(ValidationError):
            access_admin.recusar_solicitacao(pedido.id, "   ")
        access_admin.recusar_solicitacao(pedido.id, "Centro de custo não pertence ao contrato.")
        with pytest.raises(ValidationError):
            access_admin.aprovar_solicitacao(pedido.id, PERFIL_USUARIO)

    assert autenticar("obra@parceiro.test", "senha123") is None
    with database.session_scope() as session:
        pedido = session.get(SolicitacaoAcesso, pedido.id)
        assert pedido.status == access_admin.STATUS_RECUSADA and pedido.senha_hash is None
        assert session.scalar(select(Usuario).where(Usuario.email_normalizado == "obra@parceiro.test")) is None
    # Depois de recusado, a pessoa pode pedir de novo.
    _solicitar()
    assert len(_pendentes(admin)) == 1


def test_pedido_repetido_ou_de_conta_existente_nao_duplica(ambiente):
    admin = _admin()
    _solicitar()
    _solicitar()
    _solicitar("admin@oesgestao.test")
    assert [p.email_normalizado for p in _pendentes(admin)] == ["obra@parceiro.test"]


def test_somente_administrador_ve_e_decide_solicitacoes(ambiente):
    _admin()
    _solicitar()
    with database.session_scope() as session:
        pedido_id = session.scalar(select(SolicitacaoAcesso.id))
    obra = Principal(99, "obra@oesgestao.test", "Obra", PERFIL_USUARIO, 1, ())
    for principal in (obra, None):
        with usando_principal(principal):
            with pytest.raises(AuthorizationError):
                access_admin.listar_solicitacoes()
            with pytest.raises(AuthorizationError):
                access_admin.aprovar_solicitacao(pedido_id, PERFIL_CONTROLE_GERAL)
            with pytest.raises(AuthorizationError):
                access_admin.recusar_solicitacao(pedido_id, "não")
