"""Encerramento de centro de custo: solicitação com justificativa, decisão e bloqueio de novos BMs."""
from __future__ import annotations

import pytest

from sim import database
from sim.auth import (
    PERFIL_CONTROLE_GERAL,
    PERFIL_CONTROLE_GERAL,
    PERFIL_CONTROLE,
    PERFIL_USUARIO,
    Principal,
    usando_principal,
)
from sim.errors import AuthorizationError, ValidationError
from sim.services import asap, encerramento, superus
from tests.conftest import arquivo
from tests.test_access import _usuario
from tests.test_asap import CC as CC_ASAP, bm_dados
from tests.test_superus import CC as CC_SUP, mensal, semanal


def _principal(email: str, perfil: str, escopos=()) -> Principal:
    with database.session_scope() as session:
        usuario = _usuario(email, perfil)
        session.add(usuario)
        session.flush()
        return Principal(usuario.id, email, email.split("@")[0], perfil, 1, tuple(escopos))


@pytest.fixture
def cenario(ambiente):
    """Dois CCs SUPERUS e um ASAP; um usuário de obra com acesso só ao primeiro SUPERUS e ao ASAP."""
    sup_a = superus.criar_centro_custo({**CC_SUP, "titulo": "SUP-A"})
    sup_b = superus.criar_centro_custo({**CC_SUP, "titulo": "SUP-B"})
    asap_a = asap.criar_centro_custo({**CC_ASAP, "titulo": "ASAP-A"})
    return {
        "sup_a": sup_a,
        "sup_b": sup_b,
        "asap_a": asap_a,
        "obra": _principal("obra@empresa.test", PERFIL_USUARIO, (("SUPERUS", sup_a), ("ASAP", asap_a))),
        "controlador": _principal("ctrl@empresa.test", PERFIL_CONTROLE),
        "admin_geral": _principal("geral@empresa.test", PERFIL_CONTROLE_GERAL),
        "planejador": _principal("planejador@empresa.test", "planejador"),
        "faturamento": _principal("faturamento@empresa.test", "faturamento"),
    }


def test_usuario_solicita_com_justificativa_obrigatoria(cenario):
    with usando_principal(cenario["obra"]):
        with pytest.raises(ValidationError) as erro:
            encerramento.solicitar_encerramento("SUPERUS", cenario["sup_a"], "   ")
        assert "justificativa" in erro.value.errors
        encerramento.solicitar_encerramento("SUPERUS", cenario["sup_a"], "Contrato finalizado em outubro.")
        with pytest.raises(ValidationError):  # um pedido pendente por vez
            encerramento.solicitar_encerramento("SUPERUS", cenario["sup_a"], "De novo")
        [pedido] = encerramento.listar("SUPERUS", status=encerramento.PENDENTE)
        assert pedido.justificativa == "Contrato finalizado em outubro."
        assert pedido.solicitante_id == cenario["obra"].id
        # O pedido sozinho não encerra nada.
        assert superus.obter_centro_custo(cenario["sup_a"]).ativo
        superus.criar_bm_mensal(cenario["sup_a"], mensal(), [arquivo()])


def test_usuario_nao_decide_nem_pede_fora_do_seu_escopo(cenario):
    with usando_principal(cenario["obra"]):
        pedido = encerramento.solicitar_encerramento("SUPERUS", cenario["sup_a"], "Fim do contrato")
        with pytest.raises(AuthorizationError):
            encerramento.solicitar_encerramento("SUPERUS", cenario["sup_b"], "Não é meu")
        for acao in (
            lambda: encerramento.aprovar_solicitacao(pedido),
            lambda: encerramento.recusar_solicitacao(pedido, "não"),
            lambda: encerramento.encerrar("SUPERUS", cenario["sup_a"], "direto"),
            lambda: encerramento.reativar("SUPERUS", cenario["sup_a"]),
        ):
            with pytest.raises(AuthorizationError):
                acao()
        assert encerramento.contar_pendentes() == 0  # usuário de obra não decide
    with usando_principal(cenario["planejador"]):  # vê todas as obras e pede, mas não decide
        with pytest.raises(AuthorizationError):
            encerramento.aprovar_solicitacao(pedido)
        encerramento.solicitar_encerramento("SUPERUS", cenario["sup_b"], "Pedido do planejamento")
    with usando_principal(cenario["faturamento"]):  # sem área de obras: nem pede
        with pytest.raises(AuthorizationError):
            encerramento.solicitar_encerramento("ASAP", cenario["asap_a"], "Pedido do faturamento")


def test_aprovacao_encerra_e_bloqueia_novos_bms_superus(cenario):
    with usando_principal(cenario["obra"]):
        bm_existente = superus.criar_bm_mensal(cenario["sup_a"], mensal(), [arquivo()])
        pedido = encerramento.solicitar_encerramento("SUPERUS", cenario["sup_a"], "Obra entregue")
    with usando_principal(cenario["controlador"]):
        assert encerramento.contar_pendentes() == 1
        encerramento.aprovar_solicitacao(pedido, "Confere com o contrato.")
        assert encerramento.contar_pendentes() == 0

    cc = superus.obter_centro_custo(cenario["sup_a"])
    assert (cc.ativo, cc.encerramento_manual, cc.motivo_encerramento) == (False, "Sim", "Obra entregue")
    with usando_principal(cenario["obra"]):
        with pytest.raises(ValidationError) as erro:
            superus.criar_bm_mensal(cenario["sup_a"], mensal(), [arquivo()])
        assert erro.value.errors["centro_custo_id"] == encerramento.MENSAGEM_CC_INATIVO
        with pytest.raises(ValidationError):
            superus.criar_bm_semanal(cenario["sup_a"], semanal(), [arquivo()])
        # BMs já lançados continuam editáveis.
        superus.atualizar_bm_mensal(bm_existente, mensal(titulo="AJUSTADO"), [])
        [registro] = encerramento.listar("SUPERUS", cc_id=cenario["sup_a"])
        assert (registro.status, registro.parecer, registro.decidido_por_id) == (
            encerramento.APROVADA, "Confere com o contrato.", cenario["controlador"].id,
        )


def test_recusa_exige_parecer_e_mantem_ativo(cenario):
    with usando_principal(cenario["obra"]):
        pedido = encerramento.solicitar_encerramento("SUPERUS", cenario["sup_a"], "Fim")
    with usando_principal(cenario["admin_geral"]):
        with pytest.raises(ValidationError):
            encerramento.recusar_solicitacao(pedido, "")
        encerramento.recusar_solicitacao(pedido, "Ainda há medições a faturar.")
        with pytest.raises(ValidationError):
            encerramento.aprovar_solicitacao(pedido)
    assert superus.obter_centro_custo(cenario["sup_a"]).ativo
    with usando_principal(cenario["obra"]):  # depois da recusa, pode pedir de novo
        encerramento.solicitar_encerramento("SUPERUS", cenario["sup_a"], "Agora sim, contrato encerrado.")


def test_encerrar_direto_atende_pedidos_e_reativar_libera_bms(cenario):
    with usando_principal(cenario["obra"]):
        encerramento.solicitar_encerramento("SUPERUS", cenario["sup_a"], "Pedido da obra")
    with usando_principal(cenario["controlador"]):
        with pytest.raises(ValidationError):
            encerramento.encerrar("SUPERUS", cenario["sup_a"], "")
        encerramento.encerrar("SUPERUS", cenario["sup_a"], "Encerrado pelo controle")
        assert encerramento.listar("SUPERUS", status=encerramento.PENDENTE) == []
        with pytest.raises(ValidationError):
            encerramento.encerrar("SUPERUS", cenario["sup_a"], "de novo")

        encerramento.reativar("SUPERUS", cenario["sup_a"])
        cc = superus.obter_centro_custo(cenario["sup_a"])
        assert (cc.ativo, cc.encerramento_manual) == (True, "Não")
        superus.criar_bm_mensal(cenario["sup_a"], mensal(), [arquivo()])
        acoes = [(r.acao, r.status) for r in encerramento.listar("SUPERUS", cc_id=cenario["sup_a"])]
        assert sorted(acoes) == sorted([
            ("encerrar", "aprovada"), ("encerrar", "aprovada"), ("reativar", "aprovada"),
        ])


def test_asap_checkbox_ativo_e_bloqueio_de_bm(cenario):
    asap_b = asap.criar_centro_custo({**CC_ASAP, "titulo": "ASAP-B"})
    bm_id = asap.criar_bm(bm_dados(cenario["asap_a"]), [arquivo()])
    with usando_principal(cenario["admin_geral"]):
        with pytest.raises(ValidationError):  # desmarcar exige justificativa
            encerramento.definir_ativo("ASAP", asap_b, False, " ")
        encerramento.definir_ativo("ASAP", asap_b, False, "Cliente cancelou o contrato")
    assert not next(c for c in asap.listar_centros_custo() if c.id == asap_b).ativo

    with pytest.raises(ValidationError):
        asap.criar_bm(bm_dados(asap_b), [arquivo()])
    with pytest.raises(ValidationError):  # mover um BM para CC encerrado também é bloqueado
        asap.atualizar_bm(bm_id, bm_dados(asap_b), [])

    with usando_principal(cenario["admin_geral"]):
        encerramento.definir_ativo("ASAP", asap_b, True)
    asap.criar_bm(bm_dados(asap_b), [arquivo()])


def test_listagem_respeita_escopo(cenario):
    with usando_principal(cenario["controlador"]):
        encerramento.encerrar("SUPERUS", cenario["sup_b"], "Fora do escopo da obra")
    with usando_principal(cenario["obra"]):
        assert encerramento.listar("SUPERUS") == []
        with pytest.raises(AuthorizationError):
            encerramento.listar("SUPERUS", cc_id=cenario["sup_b"])
