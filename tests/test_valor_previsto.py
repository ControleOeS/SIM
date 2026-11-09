"""Valor previsto (SUPERUS) e a justificativa exigida quando o BM foge mais de 5% dele."""
from __future__ import annotations

from decimal import Decimal

import pytest

from sim.auth import PERFIL_FATURAMENTO, PERFIL_USUARIO, Principal, usando_principal
from sim.errors import AuthorizationError, ValidationError
from sim.services import previsto, superus
from tests.conftest import arquivo
from tests.test_superus import CC, mensal


@pytest.fixture
def cc(ambiente):
    cc_id = superus.criar_centro_custo(CC)
    previsto.salvar_mes("2026", "Março", {cc_id: "10.000,00"})
    return cc_id


def test_controle_preenche_altera_e_apaga_o_previsto(cc):
    assert previsto.obter(cc, "2026", "Março") == Decimal("10000.00")
    assert previsto.obter(cc, "2026", "Abril") is None
    assert previsto.salvar_mes("2026", "Março", {cc: "12.000,00"}) == 1
    assert previsto.salvar_mes("2026", "Março", {cc: Decimal("12000.00")}) == 0  # nada mudou
    assert dict((c.id, v) for c, v in previsto.listar_mes("2026", "Março"))[cc] == Decimal("12000.00")
    previsto.salvar_mes("2026", "Março", {cc: None})
    assert previsto.obter(cc, "2026", "Março") is None


def test_previsto_invalido_e_recusado(cc):
    with pytest.raises(ValidationError) as erro:
        previsto.salvar_mes("2026", "Março", {cc: "-5"})
    assert f"cc_{cc}" in erro.value.errors
    with pytest.raises(ValidationError):
        previsto.salvar_mes("2026", "Marzo", {cc: "1"})


@pytest.mark.parametrize("perfil", [PERFIL_FATURAMENTO, PERFIL_USUARIO])
def test_so_controle_altera_o_previsto(cc, perfil):
    with usando_principal(Principal(99, "x@empresa.test", "X", perfil, 1, ())):
        with pytest.raises(AuthorizationError):
            previsto.salvar_mes("2026", "Março", {cc: "1,00"})
    if perfil == PERFIL_FATURAMENTO:  # Faturamento consulta
        with usando_principal(Principal(99, "x@empresa.test", "X", perfil, 1, ())):
            assert previsto.listar_mes("2026", "Março")


@pytest.mark.parametrize("valor", ["10.500,00", "9.500,00", "10.000,00"])
def test_dentro_de_5_porcento_nao_exige_justificativa(cc, valor):
    bm_id = superus.criar_bm_mensal(cc, mensal(valor_bm=valor, justificativa_variacao="não precisa"), [arquivo()])
    bm = superus.obter_bm_mensal(bm_id)
    assert bm.valor_previsto == Decimal("10000.00") and bm.justificativa_variacao is None


def test_acima_de_5_porcento_pergunta_a_estrategia(cc):
    with pytest.raises(ValidationError) as erro:
        superus.criar_bm_mensal(cc, mensal(valor_bm="10.600,00"), [arquivo()])
    msg = erro.value.errors["justificativa_variacao"]
    assert "6% acima" in msg and "boa estratégia" in msg
    bm_id = superus.criar_bm_mensal(cc, mensal(valor_bm="10.600,00", justificativa_variacao="Turno extra"), [arquivo()])
    assert superus.obter_bm_mensal(bm_id).justificativa_variacao == "Turno extra"


def test_abaixo_de_5_porcento_pergunta_os_problemas(cc):
    with pytest.raises(ValidationError) as erro:
        superus.criar_bm_mensal(cc, mensal(valor_bm="9.000,00"), [arquivo()])
    msg = erro.value.errors["justificativa_variacao"]
    assert "10% abaixo" in msg and "problemas enfrentados" in msg and "refinado anterior" in msg


def test_sem_previsto_nao_exige_e_previsto_zero_exige(cc):
    superus.criar_bm_mensal(cc, mensal(mes_referencia="Abril", valor_bm="99.000,00"), [arquivo()])
    previsto.salvar_mes("2026", "Maio", {cc: "0"})
    with pytest.raises(ValidationError) as erro:
        superus.criar_bm_mensal(cc, mensal(mes_referencia="Maio", valor_bm="1,00"), [arquivo()])
    assert "acima do valor previsto" in erro.value.errors["justificativa_variacao"]


def test_edicao_so_recalcula_quando_valor_ou_mes_mudam(cc):
    bm_id = superus.criar_bm_mensal(cc, mensal(valor_bm="10.000,00"), [arquivo()])
    previsto.salvar_mes("2026", "Março", {cc: "50.000,00"})  # previsto mudou depois do lançamento
    superus.atualizar_bm_mensal(bm_id, mensal(valor_bm="10.000,00", titulo="Renomeado"), [])  # mesmo valor: ok
    with pytest.raises(ValidationError) as erro:
        superus.atualizar_bm_mensal(bm_id, mensal(valor_bm="10.100,00"), [])
    assert "abaixo" in erro.value.errors["justificativa_variacao"]
    superus.atualizar_bm_mensal(bm_id, mensal(valor_bm="10.100,00", justificativa_variacao="Chuvas"), [])
    bm = superus.obter_bm_mensal(bm_id)
    assert (bm.valor_previsto, bm.justificativa_variacao) == (Decimal("50000.00"), "Chuvas")
    with pytest.raises(ValidationError):  # apagar a justificativa de um BM fora da faixa não é aceito
        superus.atualizar_bm_mensal(bm_id, mensal(valor_bm="10.100,00", justificativa_variacao=""), [])
