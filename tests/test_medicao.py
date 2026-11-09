"""Período de medição a partir dos dias de início e fim (sem mês) do cadastro."""
from datetime import date

import pytest

from sim.medicao import descrever_periodo, periodo_medicao


@pytest.mark.parametrize(
    ("inicio", "fim", "ano", "mes", "esperado"),
    [
        # 1 a 31: o mês inteiro, respeitando o tamanho de cada mês
        (1, 31, 2026, 2, (date(2026, 2, 1), date(2026, 2, 28))),
        (1, 31, 2028, 2, (date(2028, 2, 1), date(2028, 2, 29))),  # ano bissexto
        (1, 31, 2026, 4, (date(2026, 4, 1), date(2026, 4, 30))),
        (1, 31, 2026, 1, (date(2026, 1, 1), date(2026, 1, 31))),
        (1, 30, 2026, 2, (date(2026, 2, 1), date(2026, 2, 28))),
        (1, 30, 2026, 3, (date(2026, 3, 1), date(2026, 3, 30))),
        # início maior que o fim: começa no mês anterior
        (21, 20, 2026, 3, (date(2026, 2, 21), date(2026, 3, 20))),
        (26, 25, 2026, 1, (date(2025, 12, 26), date(2026, 1, 25))),
        (31, 30, 2026, 3, (date(2026, 2, 28), date(2026, 3, 30))),
        # mesmo dia
        (31, 31, 2026, 2, (date(2026, 2, 28), date(2026, 2, 28))),
    ],
)
def test_periodo_medicao(inicio, fim, ano, mes, esperado):
    assert periodo_medicao(inicio, fim, ano, mes) == esperado


@pytest.mark.parametrize(("inicio", "fim"), [(0, 10), (1, 32)])
def test_dias_fora_do_intervalo(inicio, fim):
    with pytest.raises(ValueError):
        periodo_medicao(inicio, fim, 2026, 2)


def test_descrever_periodo_aceita_decimal_e_ignora_valor_invalido():
    from decimal import Decimal

    assert descrever_periodo(Decimal("1"), Decimal("31"), 2026, 2) == "01/02/2026 a 28/02/2026"
    assert descrever_periodo(None, 31, 2026, 2) == ""
    assert descrever_periodo(40, 31, 2026, 2) == ""
