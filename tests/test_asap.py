"""SIM ASAP — Engenharia e Administrativo."""
from datetime import datetime
from decimal import Decimal

import pytest

from sim.errors import NotFoundError, ValidationError
from sim.services import asap
from tests.conftest import arquivo

CC = {
    "titulo": "DEV-ASAP-001",
    "cliente": "Cliente de desenvolvimento",
    "inicio_medicao": "20",
    "fim_medicao": "19",
    "email": "dev@exemplo.invalid",
    "periodo": "Mensal",
}


def bm_dados(cc_id, **extra):
    d = {
        "centro_custo_id": cc_id,
        "titulo": "BM-DEV-01",
        "ano": "2026",
        "mes_referencia": "Janeiro",
        "status": "BM em Análise do Cliente",
        "valor_bm": "1.234,56",
        "valor_aprovado": "0",
        "glosa": "",
        "observacoes": "dado de desenvolvimento",
    }
    d.update(extra)
    return d


# 1. Centros de custo: criar, consultar, editar, excluir
def test_crud_centro_custo(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    ccs = asap.listar_centros_custo()
    assert [c.id for c in ccs] == [cc_id]
    assert ccs[0].inicio_medicao == Decimal("20")

    asap.atualizar_centro_custo(cc_id, {**CC, "cliente": "Outro cliente"})
    assert asap.listar_centros_custo()[0].cliente == "Outro cliente"

    asap.excluir_centro_custo(cc_id)
    assert asap.listar_centros_custo() == []


def test_cadastro_cc_valida_obrigatorios(ambiente):
    with pytest.raises(ValidationError) as e:
        asap.criar_centro_custo({"titulo": "", "inicio_medicao": "x"})
    assert set(e.value.errors) >= {"titulo", "cliente", "inicio_medicao", "fim_medicao", "email"}
    assert asap.listar_centros_custo() == []


@pytest.mark.parametrize("dia", ["0", "32", "1,5", "abc"])
def test_cadastro_cc_dias_de_medicao_entre_1_e_31(ambiente, dia):
    with pytest.raises(ValidationError) as e:
        asap.criar_centro_custo({**CC, "inicio_medicao": dia, "fim_medicao": dia})
    assert set(e.value.errors) == {"inicio_medicao", "fim_medicao"}


def test_cadastro_cc_aceita_dia_31(ambiente):
    cc_id = asap.criar_centro_custo({**CC, "inicio_medicao": 1, "fim_medicao": 31})
    [cc] = asap.listar_centros_custo()
    assert (cc.id, cc.inicio_medicao, cc.fim_medicao) == (cc_id, Decimal("1"), Decimal("31"))


def test_cadastro_cc_bloqueia_duplicado(ambiente):
    asap.criar_centro_custo(CC)
    with pytest.raises(ValidationError) as e:
        asap.criar_centro_custo({**CC, "titulo": "  dev-asap-001 "})
    assert "titulo" in e.value.errors


# 2. BM mensal: criar, consultar, editar, excluir
def test_crud_bm(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    bm_id = asap.criar_bm(bm_dados(cc_id), [arquivo()])
    bm = asap.obter_bm(bm_id)
    assert bm.valor_bm == Decimal("1234.56")
    assert bm.centro_custo.titulo == "DEV-ASAP-001"
    assert len(bm.anexos) == 1

    asap.atualizar_bm(bm_id, bm_dados(cc_id, titulo="BM-DEV-01-rev", glosa="10,5"), [])
    bm = asap.obter_bm(bm_id)
    assert bm.titulo == "BM-DEV-01-rev"
    assert bm.glosa == Decimal("10.50")

    asap.excluir_bm(bm_id)
    assert asap.listar_bms() == []
    with pytest.raises(NotFoundError):
        asap.obter_bm(bm_id)


def test_lista_ordenada_por_id_decrescente(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    ids = [asap.criar_bm(bm_dados(cc_id, titulo=f"BM {i}"), [arquivo()]) for i in range(3)]
    assert [b.id for b in asap.listar_bms()] == sorted(ids, reverse=True)


def test_bm_exige_obrigatorios_e_anexo(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    with pytest.raises(ValidationError) as e:
        asap.criar_bm({"centro_custo_id": cc_id, "valor_bm": "abc"}, [])
    assert set(e.value.errors) >= {"titulo", "ano", "mes_referencia", "status", "valor_bm", "valor_aprovado", "anexos"}
    assert asap.listar_bms() == []


def test_bm_rejeita_valor_negativo_e_excesso_de_casas(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    with pytest.raises(ValidationError) as e:
        asap.criar_bm(bm_dados(cc_id, valor_bm="-1", valor_aprovado="1,234"), [arquivo()])
    assert set(e.value.errors) == {"valor_bm", "valor_aprovado"}


# 6. Data de aprovação automática
def test_data_aprovacao_preenchida_ao_aprovar(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    bm_id = asap.criar_bm(bm_dados(cc_id), [arquivo()])
    assert asap.obter_bm(bm_id).data_aprovacao_cliente is None

    asap.atualizar_bm(bm_id, bm_dados(cc_id, status="BM Aprovado pelo Cliente"), [])
    data = asap.obter_bm(bm_id).data_aprovacao_cliente
    assert isinstance(data, datetime)

    # Nunca sobrescreve uma data existente
    asap.atualizar_bm(bm_id, bm_dados(cc_id, status="BM Aprovado pelo Cliente", titulo="x"), [])
    assert asap.obter_bm(bm_id).data_aprovacao_cliente == data


def test_data_aprovacao_na_inclusao(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    bm_id = asap.criar_bm(bm_dados(cc_id, status="BM Aprovado pelo Cliente"), [arquivo()])
    assert asap.obter_bm(bm_id).data_aprovacao_cliente is not None


def test_regra_pura_aprovacao_nao_sobrescreve():
    from sim.models import AsapBM

    existente = datetime(2025, 1, 1)
    bm = AsapBM(status="BM Aprovado pelo Cliente", data_aprovacao_cliente=existente)
    assert asap.aplicar_data_aprovacao(bm) is False
    assert bm.data_aprovacao_cliente == existente


# Edição preserva o CC (P-01) e nunca cria registro (defeito 11)
def test_edicao_mantem_centro_de_custo(ambiente):
    cc1 = asap.criar_centro_custo(CC)
    cc2 = asap.criar_centro_custo({**CC, "titulo": "DEV-ASAP-002"})
    bm_id = asap.criar_bm(bm_dados(cc1), [arquivo()])
    # o formulário de edição envia o CC do próprio registro
    asap.atualizar_bm(bm_id, bm_dados(cc1, titulo="novo"), [])
    assert asap.obter_bm(bm_id).centro_custo_id == cc1
    assert cc2 != cc1


def test_edicao_de_bm_inexistente_nao_cria(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    with pytest.raises(NotFoundError):
        asap.atualizar_bm(999, bm_dados(cc_id), [arquivo()])
    assert asap.listar_bms() == []


def test_edicao_exige_manter_um_anexo(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    bm_id = asap.criar_bm(bm_dados(cc_id), [arquivo()])
    anexo_id = asap.obter_bm(bm_id).anexos[0].id
    with pytest.raises(ValidationError) as e:
        asap.atualizar_bm(bm_id, bm_dados(cc_id), [], remover_anexo_ids=[anexo_id])
    assert "anexos" in e.value.errors
    assert len(asap.obter_bm(bm_id).anexos) == 1


# 5. Filtros do Faturamento ASAP
def test_filtros_faturamento(ambiente):
    cc1 = asap.criar_centro_custo(CC)
    cc2 = asap.criar_centro_custo({**CC, "titulo": "DEV-ASAP-002"})
    asap.criar_bm(bm_dados(cc1, mes_referencia="Janeiro"), [arquivo()])
    asap.criar_bm(bm_dados(cc1, mes_referencia="Fevereiro", status="BM Aprovado pelo Cliente"), [arquivo()])
    asap.criar_bm(bm_dados(cc2, mes_referencia="Janeiro"), [arquivo()])

    assert len(asap.listar_bms(centro_custo_id=cc1)) == 2
    assert len(asap.listar_bms(mes="Janeiro")) == 2
    assert len(asap.listar_bms(status="BM Aprovado pelo Cliente")) == 1
    assert len(asap.listar_bms(centro_custo_id=cc1, mes="Janeiro")) == 1
    assert len(asap.listar_bms(centro_custo_id=cc2, mes="Fevereiro")) == 0

    filtros = asap.opcoes_filtro_faturamento()
    assert filtros["status"] == ["BM Aprovado pelo Cliente", "BM em Análise do Cliente"]
    assert [c.id for c in filtros["centros"]] == [cc1, cc2]


# 7. Restrição de status do Faturamento ASAP
def test_status_faturamento_so_atual_ou_faturado_total(ambiente):
    assert asap.status_permitidos_faturamento("BM Aprovado pelo Cliente") == [
        "Faturado Total",
        "BM Aprovado pelo Cliente",
    ]
    assert asap.status_permitidos_faturamento("Faturado Total") == ["Faturado Total"]

    cc_id = asap.criar_centro_custo(CC)
    bm_id = asap.criar_bm(bm_dados(cc_id, status="BM Aprovado pelo Cliente"), [arquivo()])
    with pytest.raises(ValidationError):
        asap.atualizar_faturamento(bm_id, valor_emitido="10", status="BM em Análise do Cliente", novos_anexos=[])
    asap.atualizar_faturamento(bm_id, valor_emitido="1.000,00", status="Faturado Total", novos_anexos=[])
    bm = asap.obter_bm(bm_id)
    assert bm.status == "Faturado Total"
    assert bm.valor_emitido == Decimal("1000.00")


def test_faturamento_nao_cria_registro(ambiente):
    with pytest.raises(NotFoundError):
        asap.atualizar_faturamento(1, valor_emitido="1", status="Faturado Total", novos_anexos=[])
    assert asap.listar_bms() == []


# 8. Integridade
def test_bm_com_cc_inexistente_e_recusado(ambiente):
    with pytest.raises(ValidationError) as e:
        asap.criar_bm(bm_dados(12345), [arquivo()])
    assert "centro_custo_id" in e.value.errors


def test_cc_com_bm_nao_pode_ser_excluido(ambiente):
    cc_id = asap.criar_centro_custo(CC)
    asap.criar_bm(bm_dados(cc_id), [arquivo()])
    with pytest.raises(ValidationError):
        asap.excluir_centro_custo(cc_id)
    assert len(asap.listar_centros_custo()) == 1
