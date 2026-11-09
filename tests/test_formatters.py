from datetime import datetime
from decimal import Decimal

import pytest

from sim.formatters import (
    ValorInvalido,
    formatar_data_hora,
    formatar_moeda,
    formatar_numero,
    ler_decimal,
    normalizar_chave,
)


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("1.234,56", Decimal("1234.56")),
        ("1234,56", Decimal("1234.56")),
        ("1234.56", Decimal("1234.56")),
        ("1.234.567", Decimal("1234567")),
        ("1.500", Decimal("1500")),
        ("R$ 2.000,00", Decimal("2000.00")),
        ("-10", Decimal("-10")),
        ("0", Decimal("0")),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_ler_decimal(texto, esperado):
    assert ler_decimal(texto) == esperado


@pytest.mark.parametrize("texto", ["abc", "1,2,3", "12.34.5", "1..2", ",", "1.23,4.5"])
def test_ler_decimal_invalido(texto):
    with pytest.raises(ValorInvalido):
        ler_decimal(texto)


def test_formatar_moeda():
    assert formatar_moeda(Decimal("1234567.8")) == "1.234.567,80"
    assert formatar_moeda(Decimal("-5")) == "-5,00"
    assert formatar_moeda(0) == "0,00"
    assert formatar_moeda(None) == ""


def test_formatar_numero():
    assert formatar_numero(Decimal("15.0000")) == "15"
    assert formatar_numero(Decimal("1234.5")) == "1.234,5"
    assert formatar_numero(None) == ""


def test_formatar_data_hora_em_brasilia():
    # gravado em UTC -> exibido em America/Sao_Paulo (UTC-3)
    assert formatar_data_hora(datetime(2026, 1, 10, 15, 30)) == "10/01/2026 12:30"


def test_normalizar_chave():
    assert normalizar_chave("  CC  1001 ") == normalizar_chave("cc 1001")
