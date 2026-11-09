"""BM mensal SUPERUS: uma resposta por centro de custo e mês, com o ano definido pelo SIM."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from sim import database
from sim.errors import ValidationError
from sim.models import SuperusBMMensal
from sim.services import superus
from tests.conftest import arquivo
from tests.test_superus import CC, mensal


@pytest.mark.parametrize("mes, hoje, esperado", [
    ("Outubro", date(2026, 10, 27), "2026"),
    ("Janeiro", date(2026, 10, 27), "2026"),
    ("Dezembro", date(2027, 1, 5), "2026"),  # dezembro lançado em janeiro: ano anterior
    ("Janeiro", date(2027, 1, 5), "2027"),
    ("Março", date(2026, 3, 1), "2026"),  # disponível a partir do dia 1º
    ("Novembro", date(2026, 10, 31), None),  # mês futuro: ainda não pode
    ("Dezembro", date(2027, 2, 10), None),  # dezembro do ano anterior só em janeiro
    ("Abril", date(2026, 3, 31), None),
])
def test_ano_vem_do_mes_e_da_data_do_lancamento(mes, hoje, esperado):
    assert superus.ano_do_mes(mes, hoje) == esperado


def test_meses_disponiveis_ate_o_atual():
    assert superus.meses_permitidos(date(2026, 10, 27))[-1] == "Outubro"
    assert len(superus.meses_permitidos(date(2026, 10, 27))) == 10
    assert superus.meses_permitidos(date(2027, 1, 5)) == ["Janeiro", "Dezembro"]


def test_mes_futuro_e_recusado(ambiente):
    cc = superus.criar_centro_custo(CC)
    with pytest.raises(ValidationError) as erro:  # hoje fixado em 27/10/2026 (conftest)
        superus.criar_bm_mensal(cc, mensal(mes_referencia="Novembro"), [arquivo()])
    assert "a partir do dia 1º" in erro.value.errors["mes_referencia"]


def test_ano_digitado_e_ignorado(ambiente, monkeypatch):
    monkeypatch.setattr(superus, "_hoje", lambda: date(2027, 1, 5))
    cc = superus.criar_centro_custo(CC)
    bm_id = superus.criar_bm_mensal(cc, mensal(mes_referencia="Dezembro", ano="2030"), [arquivo()])
    assert superus.obter_bm_mensal(bm_id).ano == "2026"


def test_segundo_bm_no_mesmo_mes_e_recusado(ambiente):
    cc = superus.criar_centro_custo(CC)
    primeiro = superus.criar_bm_mensal(cc, mensal(), [arquivo()])
    with pytest.raises(ValidationError) as erro:
        superus.criar_bm_mensal(cc, mensal(tipo="PO"), [arquivo()])
    assert f"BM #{primeiro}" in erro.value.errors["mes_referencia"]
    assert "valor somado" in erro.value.errors["mes_referencia"]
    assert superus.bm_do_mes(cc, "Março") == primeiro
    outro_cc = superus.criar_centro_custo({**CC, "titulo": "OUTRO-CC"})
    superus.criar_bm_mensal(outro_cc, mensal(), [arquivo()])  # outro CC, mesmo mês: pode
    abril = superus.criar_bm_mensal(cc, mensal(mes_referencia="Abril"), [arquivo()])
    with pytest.raises(ValidationError):  # mudar para um mês ocupado também é recusado
        superus.atualizar_bm_mensal(abril, mensal(mes_referencia="Março"), [])
    with pytest.raises(ValidationError):
        superus.atualizar_faturamento(abril, status="Faturado Total", valor_liberado="", valor_emitido="",
                                      mes_referencia="Março", frs="", po="", novos_anexos=[])


def test_mes_do_historico_tambem_conta_e_repetidos_antigos_seguem_editaveis(ambiente):
    cc = superus.criar_centro_custo(CC)
    with database.session_scope() as s:  # o SIM antigo permitia dois BMs no mesmo mês
        for id_legado in (500, 501):
            s.add(SuperusBMMensal(
                id_legado=id_legado, centro_custo_id=cc, titulo=f"BM {id_legado}", numero_contrato="1",
                cidade="BH", ano="2026", mes_referencia="Março", tipo="BM", status="Faturado Total",
                valor_bm=Decimal("10"),
            ))
    with pytest.raises(ValidationError):
        superus.criar_bm_mensal(cc, mensal(), [arquivo()])
    antigo = next(b.id for b in superus.listar_bms_mensais(centro_custo_id=cc) if b.id_legado == 501)
    superus.atualizar_bm_mensal(antigo, mensal(valor_bm="10,00", titulo="Renomeado"), [])
    assert superus.obter_bm_mensal(antigo).titulo == "Renomeado"
