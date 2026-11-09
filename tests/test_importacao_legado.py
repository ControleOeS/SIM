"""Importação do histórico do SIM antigo (exportações das listas SharePoint)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import func, select

from sim import database
from sim.importacao_legado import importar
from sim.models import (
    EncerramentoCentroCusto,
    SuperusBMMensal,
    SuperusBMSemanal,
    SuperusCentroCusto,
    SuperusValorPrevisto,
)
from sim.errors import ValidationError
from sim.services import superus


def _cc(codigo, obra, coligada, **extra):
    return {
        "Title": codigo, "Obra/Cliente": obra, "Gestor de Obra": "Gestor", "Coligada": coligada,
        "Nº do Contrato": None, "Cidade": None, "Inicio de Medição": 16, "Fim de Medição": 15,
        "Meta BM": 5, "Meta FRS": 25, "Novo prazo": 1.0, "Competência de Emissão": "Seguinte",
        "Email": "g@x.test", "Email Gerente": None, "Gerente": None, "StatusCobrança": "AGUARDANDO",
        "EncerramentoManual": None, "Qtd_BMs": None, "Mês de Apuração": None, "Motivo Encerramento": None,
        **extra,
    }


def _bm(id_, cc, **extra):
    return {
        "Title": f"BM {id_}", "ID": id_, "Integração": cc, "Nº do Contrato": "4600", "Cidade": "BH",
        "Ano": 2026, "Mês de Referência": "Março", "Tipo1": "SPOT", "Valor BM": 1000.5, "Glosa": 35.5906,
        "Postergado": None, "Valor Aprovado": 900.0, "Valor Liberado": None, "Valor Emitido": None,
        "FRS": 11186585.0, "PO": "16225965", "Status": "Faturado Total", "Prazo Envio BM": None,
        "Prazo Liberação FRS": None, "Data de Faturamento": datetime(2026, 5, 7),
        "Created": datetime(2026, 4, 6, 10, 47, 59), "Modified": datetime(2026, 4, 7, 9, 0), **extra,
    }


@pytest.fixture
def pasta(tmp_path):
    def escrever(lista, linhas):
        pd.DataFrame(linhas).to_excel(tmp_path / f"Base {lista} Lists.xlsx", index=False)

    escrever("Lista de Apoio", [
        _cc(25012, "ALBRÁS ELETROMECÂNICA", "Superus Holding"),
        _cc(26007, "HYDRO ALBRAS - TELHADOS", None),  # sem coligada: deduzida pelo cliente
        _cc(25013, "ALBRÁS CIVIL", "Superus Holding"),
        _cc(26018, "HYDRO ALBRAS - ANDAIMES", None),
        _cc(26099, "HYDRO PARAGOMINAS", "Superus Holding"),
        _cc(23030, "SYLVAMO", "SUPERUS ENGENHARIA ", EncerramentoManual=True, **{"Motivo Encerramento": "Obra encerrada"}),
        _cc(1, "Cliente X Y Z", "O&S"),
    ])
    escrever("BMs", [
        _bm(10, 25012.0),
        _bm(11, None, **{"Nº do Contrato": "4600"}),  # vínculo perdido: recuperado pelo contrato
        _bm(12, 1.0),  # CC de teste
        _bm(13, None, **{"Valor BM": None, "Mês de Referência": None, "Title": None}),  # vazio
    ])
    escrever("BM Semanal", [{
        "Title": "BM SEMANA 12", "ID": 39, "Integração2": 23030, "Valor do BM": 73382.46,
        "Mês de Referência": "Abril", "Semana": "Semana 3",
        "Created": datetime(2026, 3, 21, 14, 50), "Modified": datetime(2026, 3, 21, 14, 52),
    }])
    escrever("Historico BMs", [{"ID": 1, "ID Original": 10, "Integração": 25012.0}])
    escrever("Valor Previsto", [
        {"Title": "25012", "Valor Previsto": 100.0, "Mês de Referência": "Abril"},
        {"Title": "25012", "Valor Previsto": 150.0, "Mês de Referência": "Abril"},  # repetido: vale o último
        {"Title": "99999", "Valor Previsto": 1.0, "Mês de Referência": "Abril"},  # CC inexistente
    ])
    return tmp_path


def _contar(modelo) -> int:
    with database.session_scope() as s:
        return s.scalar(select(func.count()).select_from(modelo))


def test_simulacao_nao_grava(ambiente, pasta):
    rel = importar(pasta)
    assert rel.contagem["Centros de custo importados"] == 6
    assert _contar(SuperusCentroCusto) == 0 and _contar(SuperusBMMensal) == 0


def test_importa_cc_bms_e_e_repetivel(ambiente, pasta):
    rel = importar(pasta, aplicar=True)
    assert rel.contagem["BMs mensais importados"] == 2
    assert rel.contagem["BMs semanais importados"] == 1
    assert any("26007" in a and "SUPERUS HOLDING" in a for a in rel.avisos)
    assert any("ID 11" in a and "25012" in a for a in rel.avisos)
    assert any("Cliente X Y Z" in i for i in rel.ignorados)

    with database.session_scope() as s:
        centros = {c.titulo: c for c in s.scalars(select(SuperusCentroCusto))}
        assert set(centros) == {"25012", "26007", "25013", "26018", "26099", "23030"}
        assert centros["26007"].coligada == "SUPERUS HOLDING"
        assert centros["23030"].coligada == "SUPERUS ENGENHARIA"
        assert not centros["23030"].ativo and centros["23030"].encerramento_manual == "Sim"
        assert s.scalar(select(func.count()).select_from(EncerramentoCentroCusto)) == 1

        bm = s.scalar(select(SuperusBMMensal).where(SuperusBMMensal.id_legado == 10))
        assert bm.centro_custo.titulo == "25012"
        assert (bm.valor_bm, bm.glosa, bm.frs, bm.tipo) == (Decimal("1000.50"), Decimal("35.59"), Decimal("11186585"), "SPOT")
        assert bm.data_faturamento == date(2026, 5, 7)
        assert bm.criado_em == datetime(2026, 4, 6, 13, 47, 59)  # Brasília -> UTC

    assert rel.contagem["Valores previstos importados"] == 1
    assert any("99999" in i for i in rel.ignorados)
    with database.session_scope() as s:
        assert s.scalar(select(SuperusValorPrevisto.valor)) == Decimal("150.00")

    assert importar(pasta, aplicar=True).contagem["BMs mensais já importados (mantidos)"] == 2
    assert _contar(SuperusBMMensal) == 2 and _contar(SuperusBMSemanal) == 1


def test_bm_historico_recebe_o_previsto_do_mes_sem_exigir_justificativa(ambiente, pasta):
    rel = importar(pasta, aplicar=True)
    assert rel.contagem["BMs mensais históricos ligados ao previsto do mês"] == 0  # previsto é de abril
    with database.session_scope() as s:
        s.add(SuperusValorPrevisto(centro_custo_id=s.scalar(select(SuperusCentroCusto.id).where(
            SuperusCentroCusto.titulo == "25012")), ano="2026", mes_referencia="Março", valor=Decimal("100.00")))
    assert importar(pasta, aplicar=True).contagem["BMs mensais históricos ligados ao previsto do mês"] == 2
    with database.session_scope() as s:
        bm = s.scalar(select(SuperusBMMensal).where(SuperusBMMensal.id_legado == 10))
        assert bm.valor_previsto == Decimal("100.00")  # BM de 1.000,50: muito acima, mas sem justificativa
        assert bm.atualizado_em == datetime(2026, 4, 7, 12, 0)  # data do SharePoint preservada
        bm_id = bm.id
    dados = {
        "titulo": "Renomeado", "mes_referencia": "Março", "tipo": "SPOT", "ano": "2026", "valor_bm": "1.000,50",
        "status": "Faturado Total", "cidade": "BH", "numero_contrato": "4600",
    }
    superus.atualizar_bm_mensal(bm_id, dados, [])  # editar sem mudar o valor não exige justificativa
    with pytest.raises(ValidationError):
        superus.atualizar_bm_mensal(bm_id, {**dados, "valor_bm": "1.000,00"}, [])  # mudar o valor exige


def test_bm_importado_sem_anexo_pode_ser_editado(ambiente, pasta):
    importar(pasta, aplicar=True)
    with database.session_scope() as s:
        bm = s.scalar(select(SuperusBMMensal).where(SuperusBMMensal.id_legado == 10))
        bm_id, cc_id = bm.id, bm.centro_custo_id
    dados = {
        "titulo": "BM 10 revisado", "mes_referencia": "Março", "tipo": "BM", "ano": "2026", "valor_bm": "1.000,50",
        "status": "Faturado Total", "cidade": "BH", "numero_contrato": "4600",
    }
    superus.atualizar_bm_mensal(bm_id, dados, [])
    assert superus.obter_bm_mensal(bm_id).titulo == "BM 10 revisado"
    assert superus.obter_bm_mensal(bm_id).centro_custo_id == cc_id
