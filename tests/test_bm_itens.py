"""BM mensal SUPERUS lançado BM por BM: o SIM soma o Valor BM/PO e o Valor Aprovado."""
from __future__ import annotations

from decimal import Decimal

import pytest

from sim.errors import ValidationError
from sim.services import previsto, superus
from tests.conftest import arquivo
from tests.test_superus import CC, mensal


def _dados(itens, **extra):
    d = mensal(**extra)
    d.pop("valor_bm"), d.pop("valor_aprovado", None)
    return {**d, "itens": itens}


def test_totais_sao_a_soma_dos_bms(ambiente):
    cc = superus.criar_centro_custo(CC)
    bm_id = superus.criar_bm_mensal(cc, _dados([
        {"descricao": "BM 33 OPEX", "valor_bm": Decimal("1000.50"), "valor_aprovado": Decimal("900")},
        {"descricao": "BM 25 CAPEX", "valor_bm": "2.000,00", "valor_aprovado": None},
        {"descricao": None, "valor_bm": None, "valor_aprovado": None},  # linha vazia é ignorada
    ]), [arquivo()])
    bm = superus.obter_bm_mensal(bm_id)
    assert (bm.valor_bm, bm.valor_aprovado) == (Decimal("3000.50"), Decimal("900.00"))
    assert [(i.ordem, i.descricao) for i in bm.itens] == [(1, "BM 33 OPEX"), (2, "BM 25 CAPEX")]

    superus.atualizar_bm_mensal(bm_id, _dados([{"descricao": "BM único", "valor_bm": "10,00", "valor_aprovado": ""}]), [])
    bm = superus.obter_bm_mensal(bm_id)
    assert (bm.valor_bm, bm.valor_aprovado, len(bm.itens)) == (Decimal("10.00"), None, 1)


@pytest.mark.parametrize("itens, trecho", [
    ([], "pelo menos um BM"),
    ([{"descricao": "", "valor_bm": "10", "valor_aprovado": None}], "BM 1: identificação"),
    ([{"descricao": "BM 1", "valor_bm": None, "valor_aprovado": "5"}], "BM 1: valor do BM"),
    ([{"descricao": "A", "valor_bm": "1"}, {"descricao": "B", "valor_bm": "-3"}], "BM 2: valor do BM"),
])
def test_bms_incompletos_sao_recusados(ambiente, itens, trecho):
    cc = superus.criar_centro_custo(CC)
    with pytest.raises(ValidationError) as erro:
        superus.criar_bm_mensal(cc, _dados(itens), [arquivo()])
    assert trecho in erro.value.errors["itens"]


def test_variacao_usa_a_soma_dos_bms(ambiente):
    cc = superus.criar_centro_custo(CC)
    previsto.salvar_mes("2026", "Março", {cc: "10.000,00"})
    itens = [{"descricao": "BM A", "valor_bm": "6.000,00"}, {"descricao": "BM B", "valor_bm": "4.200,00"}]
    superus.criar_bm_mensal(cc, _dados(itens), [arquivo()])  # 10.200: dentro dos 5%

    previsto.salvar_mes("2026", "Abril", {cc: "10.000,00"})
    acima = [{"descricao": "BM A", "valor_bm": "6.000,00"}, {"descricao": "BM B", "valor_bm": "6.000,00"}]
    with pytest.raises(ValidationError) as erro:  # 12.000: 20% acima
        superus.criar_bm_mensal(cc, _dados(acima, mes_referencia="Abril"), [arquivo()])
    assert "20% acima" in erro.value.errors["justificativa_variacao"]
