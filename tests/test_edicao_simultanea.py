"""Vários usuários gravando ao mesmo tempo: nenhuma alteração pode se perder em silêncio.

- Bloqueio otimista: cada registro editável tem `versao`; quem grava com a versão desatualizada
  recebe ConflictError e nada é gravado (inclusive na corrida entre a leitura e o commit).
- Pedidos pendentes (encerramento, acesso) são únicos por índice no banco, não só por consulta.
- SQLite ocupado vira mensagem compreensível.
"""
from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from streamlit.testing.v1 import AppTest

from sim import access_admin, database
from sim.auth import PERFIL_CONTROLE, usando_principal
from sim.errors import ConflictError, PersistenceError, ValidationError
from sim.models import AsapBM, DominioPermitido, EncerramentoCentroCusto, SolicitacaoAcesso, SuperusBMMensal
from sim.services import asap, common, encerramento, superus
from tests.conftest import arquivo
from tests.test_asap import CC as CC_ASAP, bm_dados
from tests.test_encerramento import _principal
from tests.test_superus import CC as CC_SUP, mensal, semanal


@pytest.fixture
def bm_sup(ambiente):
    cc_id = superus.criar_centro_custo(CC_SUP)
    bm_id = superus.criar_bm_mensal(cc_id, mensal(), [arquivo()])
    return cc_id, bm_id


def _versao(modelo, id_: int) -> int:
    with database.session_scope() as s:
        return s.get(modelo, id_).versao


def _gravar_por_fora(modelo, id_: int, **campos) -> None:
    """Simula outra pessoa gravando em outra conexão (já confirmada)."""
    with database.session_scope() as s:
        registro = s.get(modelo, id_)
        for k, v in campos.items():
            setattr(registro, k, v)


def test_versao_desatualizada_e_recusada_sem_gravar_nada(bm_sup):
    cc_id, bm_id = bm_sup
    lida = _versao(SuperusBMMensal, bm_id)
    assert lida == 1

    # Ana grava primeiro, com a versão que abriu.
    superus.atualizar_bm_mensal(bm_id, mensal(valor_bm="10.000,00"), [], versao=lida)
    assert _versao(SuperusBMMensal, bm_id) == 2

    # Bruno abriu o mesmo BM antes e tenta gravar só a cidade: recusado, o valor da Ana fica.
    with pytest.raises(ConflictError) as erro:
        superus.atualizar_bm_mensal(bm_id, mensal(cidade="Manaus"), [arquivo("novo.pdf")], versao=lida)
    assert "Cancelar" in erro.value.message
    bm = superus.obter_bm_mensal(bm_id)
    assert (str(bm.valor_bm), bm.cidade, len(bm.anexos)) == ("10000.00", mensal()["cidade"], 1)

    # Depois de recarregar (versão atual), a gravação passa.
    superus.atualizar_bm_mensal(bm_id, mensal(valor_bm="10.000,00", cidade="Manaus"), [], versao=2)
    assert superus.obter_bm_mensal(bm_id).cidade == "Manaus"


def test_so_anexos_tambem_avanca_a_versao(bm_sup):
    _, bm_id = bm_sup
    superus.atualizar_bm_mensal(bm_id, mensal(), [arquivo("extra.pdf")], versao=1)
    assert _versao(SuperusBMMensal, bm_id) == 2
    with pytest.raises(ConflictError):  # quem abriu antes não remove o último anexo de outra pessoa
        superus.atualizar_bm_mensal(bm_id, mensal(), [], [superus.obter_bm_mensal(bm_id).anexos[0].id], versao=1)


def test_corrida_entre_leitura_e_gravacao_vira_conflito(bm_sup, monkeypatch):
    """Outra pessoa grava depois de a versão ser conferida e antes do commit: o banco recusa."""
    _, bm_id = bm_sup
    original = superus.conferir_versao

    def conferir_e_alguem_grava(registro, versao_lida):
        original(registro, versao_lida)
        _gravar_por_fora(SuperusBMMensal, bm_id, titulo="GRAVADO POR OUTRA PESSOA")

    monkeypatch.setattr(superus, "conferir_versao", conferir_e_alguem_grava)
    with pytest.raises(ConflictError):
        superus.atualizar_bm_mensal(bm_id, mensal(titulo="MEU"), [arquivo("meu.pdf")], versao=1)
    monkeypatch.undo()
    bm = superus.obter_bm_mensal(bm_id)
    assert (bm.titulo, len(bm.anexos)) == ("GRAVADO POR OUTRA PESSOA", 1)  # anexo novo descartado


def test_faturamento_adm_e_engenharia_no_mesmo_bm(bm_sup):
    _, bm_id = bm_sup
    superus.atualizar_faturamento(
        bm_id, status=mensal()["status"], valor_liberado="", valor_emitido="500,00", mes_referencia="Março",
        frs="", po="PO-1", novos_anexos=[], versao=1,
    )
    with pytest.raises(ConflictError):
        superus.atualizar_bm_mensal(bm_id, mensal(), [], versao=1)
    assert superus.obter_bm_mensal(bm_id).po == "PO-1"


def test_exclusao_de_registro_alterado_por_outro_e_recusada(bm_sup):
    cc_id, bm_id = bm_sup
    superus.atualizar_bm_mensal(bm_id, mensal(titulo="ALTERADO"), [], versao=1)
    with pytest.raises(ConflictError):
        superus.excluir_bm_mensal(bm_id, versao=1)
    superus.excluir_bm_mensal(bm_id, versao=2)

    sem_id = superus.criar_bm_semanal(cc_id, semanal(), [arquivo()])
    superus.atualizar_bm_semanal(sem_id, semanal(valor_bm="3.000,00"), [], versao=1)
    with pytest.raises(ConflictError):
        superus.atualizar_bm_semanal(sem_id, semanal(), [], versao=1)
    with pytest.raises(ConflictError):
        superus.excluir_bm_semanal(sem_id, versao=1)


def test_asap_bm_faturamento_e_centro_de_custo(ambiente):
    cc_id = asap.criar_centro_custo(CC_ASAP)
    bm_id = asap.criar_bm(bm_dados(cc_id), [arquivo()])
    asap.atualizar_faturamento(bm_id, valor_emitido="1,00", status=bm_dados(cc_id)["status"], novos_anexos=[],
                               versao=1)
    with pytest.raises(ConflictError):
        asap.atualizar_bm(bm_id, bm_dados(cc_id), [], versao=1)
    with pytest.raises(ConflictError):
        asap.excluir_bm(bm_id, versao=1)
    assert _versao(AsapBM, bm_id) == 2

    asap.atualizar_centro_custo(cc_id, {**CC_ASAP, "cliente": "Novo"}, versao=1)
    with pytest.raises(ConflictError):
        asap.atualizar_centro_custo(cc_id, CC_ASAP, versao=1)

    sup_id = superus.criar_centro_custo(CC_SUP)
    superus.atualizar_dados_cc(sup_id, qtd_bms="3", cidade="Belém", numero_contrato="1/2026", versao=1)
    with pytest.raises(ConflictError):
        superus.atualizar_dados_cc(sup_id, qtd_bms="4", cidade="", numero_contrato="", versao=1)
    with pytest.raises(ConflictError):
        superus.atualizar_cadastro(sup_id, CC_SUP, versao=1)


def test_encerrar_centro_avanca_a_versao_do_cadastro(ambiente):
    sup_id = superus.criar_centro_custo(CC_SUP)
    with usando_principal(_principal("ctrl@empresa.test", PERFIL_CONTROLE)):
        encerramento.encerrar("SUPERUS", sup_id, "Fim do contrato")
    with pytest.raises(ConflictError):  # formulário aberto antes do encerramento
        superus.atualizar_dados_cc(sup_id, qtd_bms="1", cidade="", numero_contrato="", versao=1)


# ------------------------------------------------- pedidos pendentes únicos ----


def test_indice_impede_dois_pedidos_de_encerramento_pendentes(ambiente):
    sup_id = superus.criar_centro_custo(CC_SUP)
    empresa_id = superus.obter_centro_custo(sup_id).empresa_id
    with pytest.raises(IntegrityError):
        with database.session_scope() as s:
            for _ in range(2):
                s.add(EncerramentoCentroCusto(empresa_id=empresa_id, superus_cc_id=sup_id, acao="encerrar",
                                              status="pendente", justificativa="x"))
    with database.session_scope() as s:  # recusados/aprovados não contam
        for status in ("recusada", "recusada", "pendente"):
            s.add(EncerramentoCentroCusto(empresa_id=empresa_id, superus_cc_id=sup_id, acao="encerrar",
                                          status=status, justificativa="x"))


def test_pedidos_de_encerramento_simultaneos(ambiente, monkeypatch):
    """Dois pedidos passam pela consulta ao mesmo tempo: o segundo vira mensagem, não erro técnico."""
    sup_id = superus.criar_centro_custo(CC_SUP)
    empresa_id = superus.obter_centro_custo(sup_id).empresa_id
    original = encerramento._novo_registro

    def outro_pedido_antes(session, empresa, cc_id, **campos):
        with database.session_scope() as s:
            s.add(EncerramentoCentroCusto(empresa_id=empresa_id, superus_cc_id=sup_id, acao="encerrar",
                                          status="pendente", justificativa="pedido do colega"))
        return original(session, empresa, cc_id, **campos)

    monkeypatch.setattr(encerramento, "_novo_registro", outro_pedido_antes)
    with pytest.raises(ValidationError) as erro:
        encerramento.solicitar_encerramento("SUPERUS", sup_id, "Meu pedido")
    assert "aguardando aprovação" in erro.value.errors["centro_custo"]
    monkeypatch.undo()
    assert [p.justificativa for p in encerramento.listar("SUPERUS", status=encerramento.PENDENTE)] == [
        "pedido do colega"
    ]


def test_solicitacao_de_acesso_pendente_unica(ambiente, monkeypatch):
    def novo():
        return SolicitacaoAcesso(nome="A", email="a@e.test", email_normalizado="a@e.test", senha_hash="x",
                                 perfil_solicitado="usuario", centro_custo_informado="CC", status="pendente")

    with pytest.raises(IntegrityError):
        with database.session_scope() as s:
            s.add_all([novo(), novo()])

    def corrida(*_args):
        raise IntegrityError("INSERT", {}, sqlite3.IntegrityError("UNIQUE constraint failed"))

    # Pedido simultâneo do mesmo e-mail: resposta igual à de "pedido já existente".
    with database.session_scope() as s:
        s.add(DominioPermitido(dominio="empresa.test", ativo=True))
    monkeypatch.setattr(access_admin, "_registrar_solicitacao", corrida)
    assert access_admin.solicitar_acesso("A", "a@empresa.test", "senha-forte-1", "senha-forte-1", "usuario",
                                         "CC 1") is None


# ------------------------------------------------------------ SQLite ----


def test_banco_ocupado_vira_mensagem_compreensivel(ambiente):
    with pytest.raises(PersistenceError) as erro:
        with common.transacao("teste"):
            raise OperationalError("UPDATE", {}, sqlite3.OperationalError("database is locked"))
    assert common.MSG_OCUPADO in erro.value.message


def test_sqlite_em_modo_wal(ambiente):
    with database.get_engine().connect() as c:
        modo = c.exec_driver_sql("PRAGMA journal_mode").scalar()
        espera = c.exec_driver_sql("PRAGMA busy_timeout").scalar()
    assert (modo, espera) == ("wal", database.SQLITE_ESPERA_SEGUNDOS * 1000)


# --------------------------------------------------------------- tela ----


def _script_versao_lida():
    import streamlit as st

    from sim.ui import common as ui

    class Registro:
        versao = st.session_state.get("versao_no_banco", 1)

    editando = st.session_state.get("editando", True)
    st.session_state["lida"] = ui.versao_lida("ns", Registro() if editando else None, 7)
    if st.session_state.get("reiniciar"):
        st.session_state["reiniciar"] = False
        ui.reiniciar("ns")


def test_tela_guarda_a_versao_aberta_ate_gravar_ou_cancelar():
    at = AppTest.from_function(_script_versao_lida).run()
    assert at.session_state["lida"] == 1
    at.session_state["versao_no_banco"] = 2  # outra pessoa gravou; o formulário continua com a versão aberta
    at.run()
    assert at.session_state["lida"] == 1
    at.session_state["reiniciar"] = True  # gravou ou cancelou: novas chaves de formulário
    at.run()
    at.run()
    assert at.session_state["lida"] == 2
    at.session_state["versao_no_banco"] = 3
    at.session_state["editando"] = False  # desmarcou a linha: esquece
    at.run()
    at.session_state["editando"] = True
    at.run()
    assert at.session_state["lida"] == 3
