"""Perfis e permissões (decisão do responsável em 2026-10-27).

- Usuário de obras: só os centros liberados; BMs e encerramento (pedido); sem área administrativa.
- Planejador: todas as obras, todas as atividades de obra; sem área administrativa nem decisões de controle.
- Faturamento: só a área administrativa, com todas as obras das duas coligadas.
- Controle: aprova acessos, libera centros, desativa contas, decide encerramentos; todas as obras e o
  administrativo. Não mexe em domínios, senhas nem em contas de nível Controle.
- Controle Geral: tudo.
"""
from __future__ import annotations

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from sim import access_admin, database
from sim.auth import (
    PERFIL_CONTROLE,
    PERFIL_CONTROLE_GERAL,
    PERFIL_FATURAMENTO,
    PERFIL_PLANEJADOR,
    PERFIL_USUARIO,
    Principal,
    usando_principal,
)
from sim.errors import AuthorizationError, ValidationError
from sim.models import AcessoCentroCusto, DominioPermitido, Empresa, SolicitacaoAcesso
from sim.services import asap, superus
from tests.conftest import arquivo
from tests.test_access import _usuario
from tests.test_asap import CC as CC_ASAP, bm_dados
from tests.test_superus import CC as CC_SUP, mensal
from tests.test_telas import APP, _links, _sem_erros


def _conta(email: str, perfil: str, escopos=()) -> Principal:
    with database.session_scope() as session:
        usuario = _usuario(email, perfil)
        session.add(usuario)
        session.flush()
        return Principal(usuario.id, email, email.split("@")[0], perfil, 1, tuple(escopos))


@pytest.fixture
def cenario(ambiente):
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
    sup = superus.criar_centro_custo(CC_SUP)
    asap_cc = asap.criar_centro_custo(CC_ASAP)
    return {
        "sup": sup,
        "asap": asap_cc,
        "bm_sup": superus.criar_bm_mensal(sup, mensal(), [arquivo()]),
        "bm_asap": asap.criar_bm(bm_dados(asap_cc), [arquivo()]),
        "obra": _conta("obra@empresa.test", PERFIL_USUARIO, (("SUPERUS", sup),)),
        "planejador": _conta("plan@empresa.test", PERFIL_PLANEJADOR),
        "faturamento": _conta("fat@empresa.test", PERFIL_FATURAMENTO),
        "controle": _conta("ctrl@empresa.test", PERFIL_CONTROLE),
        "geral": _conta("geral@empresa.test", PERFIL_CONTROLE_GERAL),
    }


def _faturar_sup(bm_id):
    superus.atualizar_faturamento(
        bm_id, status=mensal()["status"], valor_liberado="", valor_emitido="1,00", mes_referencia="Março",
        frs="", po="", novos_anexos=[],
    )


# ---------------------------------------------------------------- serviços ----


def test_usuario_de_obras_sem_area_administrativa(cenario):
    with usando_principal(cenario["obra"]):
        superus.atualizar_bm_mensal(cenario["bm_sup"], mensal(titulo="EDITADO"), [])  # sua obra: edita
        for acao in (
            lambda: _faturar_sup(cenario["bm_sup"]),  # nem no próprio centro
            superus.opcoes_filtro_faturamento,
            lambda: superus.atualizar_dados_cc(cenario["sup"], qtd_bms="1", cidade="", numero_contrato=""),
            lambda: asap.criar_bm(bm_dados(cenario["asap"]), [arquivo()]),  # centro não liberado
        ):
            with pytest.raises(AuthorizationError):
                acao()


def test_planejador_faz_tudo_de_obra_em_todas_as_obras(cenario):
    with usando_principal(cenario["planejador"]):
        superus.criar_bm_mensal(cenario["sup"], mensal(mes_referencia="Abril"), [arquivo()])  # Março já tem BM
        asap.criar_bm(bm_dados(cenario["asap"]), [arquivo()])
        assert {c.id for c in superus.listar_centros_custo()} == {cenario["sup"]}
        for acao in (
            lambda: _faturar_sup(cenario["bm_sup"]),
            asap.opcoes_filtro_faturamento,
            lambda: superus.criar_centro_custo({**CC_SUP, "titulo": "NOVO"}),  # cadastro é do Controle
            lambda: access_admin.listar_solicitacoes(),
        ):
            with pytest.raises(AuthorizationError):
                acao()


def test_faturamento_so_na_area_administrativa_das_duas_coligadas(cenario):
    with usando_principal(cenario["faturamento"]):
        _faturar_sup(cenario["bm_sup"])
        asap.atualizar_faturamento(cenario["bm_asap"], valor_emitido="2,00", status=bm_dados(0)["status"],
                                   novos_anexos=[])
        superus.atualizar_dados_cc(cenario["sup"], qtd_bms="2", cidade="Belém", numero_contrato="1")
        assert superus.listar_bms_mensais()  # enxerga todas as obras
        for acao in (
            lambda: superus.criar_bm_mensal(cenario["sup"], mensal(), [arquivo()]),
            lambda: superus.atualizar_bm_mensal(cenario["bm_sup"], mensal(), []),
            lambda: asap.excluir_bm(cenario["bm_asap"]),
            lambda: access_admin.listar_usuarios(),
        ):
            with pytest.raises(AuthorizationError):
                acao()


def test_controle_tem_obras_administrativo_e_cadastro(cenario):
    with usando_principal(cenario["controle"]):
        superus.criar_bm_mensal(cenario["sup"], mensal(mes_referencia="Abril"), [arquivo()])  # Março já tem BM
        _faturar_sup(cenario["bm_sup"])
        asap.criar_centro_custo({**CC_ASAP, "titulo": "NOVO-ASAP"})


# --------------------------------------------------------- controle de acesso ----


def test_controle_aprova_libera_e_desativa_mas_nao_tem_controle_total(cenario):
    with usando_principal(cenario["controle"]):
        novo_id, _ = access_admin.criar_usuario("novo@empresa.test", "Novo", PERFIL_USUARIO,
                                                [("SUPERUS", cenario["sup"])])
        access_admin.conceder_acesso(novo_id, "ASAP", cenario["asap"])
        access_admin.alterar_perfil(novo_id, PERFIL_PLANEJADOR)
        access_admin.definir_usuario_ativo(novo_id, False)
        assert [d.dominio for d in access_admin.listar_dominios()] == ["empresa.test"]  # vê, não mexe

        for acao in (
            lambda: access_admin.adicionar_dominio("outra.test"),
            lambda: access_admin.desativar_dominio(access_admin.listar_dominios()[0].id),
            lambda: access_admin.redefinir_senha(cenario["obra"].id),
            lambda: access_admin.criar_usuario("c2@empresa.test", "C2", PERFIL_CONTROLE),
            lambda: access_admin.alterar_perfil(cenario["obra"].id, PERFIL_CONTROLE),
            lambda: access_admin.alterar_perfil(cenario["geral"].id, PERFIL_USUARIO),
            lambda: access_admin.definir_usuario_ativo(cenario["geral"].id, False),
        ):
            with pytest.raises(AuthorizationError):
                acao()


def test_controle_aprova_pedido_mas_so_controle_geral_concede_controle(cenario):
    with usando_principal(None):
        access_admin.solicitar_acesso("Pessoa", "pessoa@empresa.test", "senha-boa-1", "senha-boa-1",
                                      PERFIL_CONTROLE, "CC 1")
    with database.session_scope() as session:
        pedido_id = session.query(SolicitacaoAcesso.id).scalar()
    with usando_principal(cenario["controle"]):
        with pytest.raises(AuthorizationError):
            access_admin.aprovar_solicitacao(pedido_id, PERFIL_CONTROLE)
        access_admin.aprovar_solicitacao(pedido_id, PERFIL_FATURAMENTO, parecer="Classificação ajustada.")


def test_controle_geral_faz_tudo_e_nunca_fica_sem_controle_geral(cenario):
    with usando_principal(cenario["geral"]):
        access_admin.adicionar_dominio("outra.test")
        access_admin.redefinir_senha(cenario["obra"].id)
        access_admin.alterar_perfil(cenario["controle"].id, PERFIL_CONTROLE_GERAL)
        access_admin.alterar_perfil(cenario["controle"].id, PERFIL_CONTROLE)
        with pytest.raises(ValidationError):  # única conta Controle Geral
            access_admin.alterar_perfil(cenario["geral"].id, PERFIL_CONTROLE)


# -------------------------------------------------------------------- telas ----


@pytest.mark.parametrize("perfil, areas, controle_acesso, trocar_senha", [
    (PERFIL_USUARIO, ["superus"], False, False),
    (PERFIL_PLANEJADOR, ["asap", "superus"], False, False),
    (PERFIL_FATURAMENTO, ["administrativo"], False, False),
    (PERFIL_CONTROLE, ["asap", "superus", "administrativo"], True, True),
    (PERFIL_CONTROLE_GERAL, ["asap", "superus", "administrativo"], True, True),
])
def test_areas_visiveis_por_perfil(ambiente, perfil, areas, controle_acesso, trocar_senha):
    st.cache_resource.clear()
    sup = superus.criar_centro_custo(CC_SUP)
    asap.criar_centro_custo(CC_ASAP)
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        usuario = _usuario("conta@empresa.test", perfil)
        session.add(usuario)
        session.flush()
        usuario_id = usuario.id
    if perfil == PERFIL_USUARIO:  # usuário de obras com um centro SUPERUS liberado
        with database.session_scope() as session:
            empresa_id = session.query(Empresa.id).filter(Empresa.codigo == "SUPERUS").scalar()
            session.add(AcessoCentroCusto(usuario_id=usuario_id, empresa_id=empresa_id, superus_centro_custo_id=sup))

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = usuario_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    _sem_erros(at)
    destinos = {"asap": "asap", "superus": "superus", "administrativo": "administrativo"}
    assert [pagina for _, pagina in _links(at) if pagina in destinos.values()] == [destinos[a] for a in areas]
    lateral = [pagina for _, pagina in _links(at, "sidebar")]
    assert ("controle-acesso" in lateral) is controle_acesso
    assert any(b.label == "Trocar senha" for b in at.sidebar.button) is trocar_senha
    if perfil == PERFIL_FATURAMENTO:
        at.switch_page("telas/adm_selecao.py").run()
        _sem_erros(at)
        assert [p for _, p in _links(at)] == ["asap-adm", "superus-adm", ""]  # as duas coligadas
