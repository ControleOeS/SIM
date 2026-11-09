"""Período de medição a partir dos dias de início e fim cadastrados no centro de custo.

O cadastro guarda só o dia do mês (1 a 31), sem mês. Para um mês de referência:
- dia maior que o tamanho do mês vale o último dia dele (31 em fevereiro = 28 ou 29;
  31 em abril = 30);
- início <= fim: o período fica dentro do próprio mês (1 a 31 em fevereiro = 01/02 a 28/02);
- início > fim: o período começa no mês anterior (21 a 20 em março = 21/02 a 20/03).
"""
from __future__ import annotations

import calendar
from datetime import date

DIAS_MES = tuple(range(1, 32))

AJUDA_DIA = (
    "Dia do mês (1 a 31). Se o mês tiver menos dias, vale o último dia dele: "
    "31 em fevereiro = dia 28 (ou 29); 31 em abril = dia 30."
)
EXEMPLOS_PERIODO = (
    "Exemplos: início 1 e fim 31 = do primeiro ao último dia de cada mês (em fevereiro, 01 a 28). "
    "Início maior que o fim (ex.: 21 e 20) = do dia 21 do mês anterior ao dia 20 do mês."
)


def _dia_no_mes(ano: int, mes: int, dia: int) -> date:
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def periodo_medicao(inicio: int, fim: int, ano: int, mes: int) -> tuple[date, date]:
    """Datas de início e fim da medição cujo fechamento cai no mês/ano informado."""
    inicio, fim = int(inicio), int(fim)
    if inicio not in DIAS_MES or fim not in DIAS_MES:
        raise ValueError("Os dias de medição devem estar entre 1 e 31.")
    data_fim = _dia_no_mes(ano, mes, fim)
    if inicio <= fim:
        return _dia_no_mes(ano, mes, inicio), data_fim
    ano_ini, mes_ini = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return _dia_no_mes(ano_ini, mes_ini, inicio), data_fim


def descrever_periodo(inicio, fim, ano: int, mes: int) -> str:
    """Texto curto, ex.: '01/02/2026 a 28/02/2026'; vazio se os dias não forem válidos."""
    try:
        de, ate = periodo_medicao(int(inicio), int(fim), ano, mes)
    except (TypeError, ValueError):
        return ""
    return f"{de:%d/%m/%Y} a {ate:%d/%m/%Y}"
