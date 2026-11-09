"""SIM SUPERUS e SIM SUPERUS — Administrativo."""
from decimal import Decimal

import pytest

from sim.errors import NotFoundError, ValidationError
from sim.services import superus
from tests.conftest import arquivo

CC = {
    "coligada": "SUPERUS ENGENHARIA",
    "titulo": "DEV-SUP-100",
    "gestor_obra": "Gestor de desenvolvimento",
    "obra_cliente": "OBRA DE DESENVOLVIMENTO",
    "inicio_medicao": "21",
    "fim_medicao": "20",
}


def mensal(**extra):
    d = {
        "titulo": "BM-SUP-DEV",
        "mes_referencia": "Março",
        "tipo": "BM",
        "ano": "2026",
        "valor_bm": "10.000,00",
        "glosa": "100",
        "postergado": "50",
        "valor_aprovado": "9.850,00",
        "status": "BM em Análise do Cliente",
        "cidade": "Cidade DEV",
        "numero_contrato": "CT-DEV-1",
        "po": "PO-4500-ABC",
    }
    d.update(extra)
    return d


def semanal(**extra):
    d = {"titulo": "SEM-DEV", "mes_referencia": "Março", "semana": "Semana 1", "valor_bm": "2.500,00"}
    d.update(extra)
    return d


# 1. CRUD de centro de custo (SUPERUS)
def test_crud_centro_custo(ambiente):
    cc_id = superus.criar_centro_custo(CC)
    cc = superus.obter_centro_custo(cc_id)
    assert (cc.gestor_obra, cc.obra_cliente, cc.coligada) == (
        "Gestor de desenvolvimento",
        "OBRA DE DESENVOLVIMENTO",
        "SUPERUS ENGENHARIA",
    )
    superus.atualizar_cadastro(cc_id, {**CC, "gestor_obra": "Novo gestor"})
    assert superus.obter_centro_custo(cc_id).gestor_obra == "Novo gestor"
    superus.excluir_centro_custo(cc_id)
    assert superus.listar_centros_custo() == []


def test_cadastro_obrigatorios(ambiente):
    with pytest.raises(ValidationError) as e:
        superus.criar_centro_custo({})
    assert set(e.value.errors) == {
        "coligada", "titulo", "gestor_obra", "obra_cliente", "inicio_medicao", "fim_medicao"
    }


def test_cadastro_duplicidade_por_codigo(ambiente):
    superus.criar_centro_custo(CC)
    with pytest.raises(ValidationError):
        superus.criar_centro_custo({**CC, "titulo": "dev-sup-100  "})
    # códigos diferentes são permitidos
    superus.criar_centro_custo({**CC, "titulo": "DEV-SUP-101"})
    assert len(superus.listar_centros_custo()) == 2


def test_coligada_e_uma_das_tres_do_grupo_superus(ambiente):
    """O módulo SUPERUS reúne Superus Engenharia, ACPL e Superus Holding (decisão de 2026-10-27)."""
    ids = [
        superus.criar_centro_custo({**CC, "titulo": f"CC-{i}", "coligada": coligada})
        for i, coligada in enumerate(superus.COLIGADAS)
    ]
    assert sorted(c.coligada for c in superus.listar_centros_custo()) == sorted(superus.COLIGADAS)
    for coligada in ("ASAP", "SUPERUS", ""):
        with pytest.raises(ValidationError) as erro:
            superus.criar_centro_custo({**CC, "titulo": "CC-X", "coligada": coligada})
        assert "coligada" in erro.value.errors
    superus.atualizar_cadastro(ids[0], {**CC, "titulo": "CC-0", "coligada": "ACPL"})
    assert superus.obter_centro_custo(ids[0]).coligada == "ACPL"


@pytest.mark.parametrize("dia", ["0", "32", "1,5", "abc", "-3"])
def test_dias_de_medicao_entre_1_e_31(ambiente, dia):
    with pytest.raises(ValidationError) as e:
        superus.criar_centro_custo({**CC, "inicio_medicao": dia, "fim_medicao": dia})
    assert set(e.value.errors) == {"inicio_medicao", "fim_medicao"}


def test_dias_de_medicao_aceitam_numero_inteiro(ambiente):
    cc_id = superus.criar_centro_custo({**CC, "inicio_medicao": 1, "fim_medicao": 31})
    cc = superus.obter_centro_custo(cc_id)
    assert (cc.inicio_medicao, cc.fim_medicao) == (Decimal("1"), Decimal("31"))


# 2. CRUD de BM mensal (SUPERUS)
def test_crud_bm_mensal(ambiente):
    cc_id = superus.criar_centro_custo(CC)
    bm_id = superus.criar_bm_mensal(cc_id, mensal(), [arquivo()])
    bm = superus.obter_bm_mensal(bm_id)
    assert bm.centro_custo_id == cc_id
    assert bm.valor_bm == Decimal("10000.00")
    assert bm.postergado == Decimal("50")

    superus.atualizar_bm_mensal(bm_id, mensal(status="BM Aprovado pelo Cliente"), [])
    bm = superus.obter_bm_mensal(bm_id)
    assert bm.status == "BM Aprovado pelo Cliente"
    assert bm.centro_custo_id == cc_id

    superus.excluir_bm_mensal(bm_id)
    assert superus.listar_bms_mensais(centro_custo_id=cc_id) == []


# 7. Restrição de status da engenharia SUPERUS
def test_status_engenharia_restrito(ambiente):
    cc_id = superus.criar_centro_custo(CC)
    with pytest.raises(ValidationError) as e:
        superus.criar_bm_mensal(cc_id, mensal(status="Faturado Total"), [arquivo()])
    assert "status" in e.value.errors


def test_status_gravado_pelo_adm_pode_ser_mantido_na_edicao(ambiente, monkeypatch):
    cc_id = superus.criar_centro_custo(CC)
    bm_id = superus.criar_bm_mensal(cc_id, mensal(), [arquivo()])
    # simula um status definido pelo faturamento que não é opção da engenharia
    from sim.database import session_scope
    from sim.models import SuperusBMMensal

    with session_scope() as s:
        s.get(SuperusBMMensal, bm_id).status = "Status do faturamento"
    superus.atualizar_bm_mensal(bm_id, mensal(status="Status do faturamento", titulo="x"), [])
    assert superus.obter_bm_mensal(bm_id).status == "Status do faturamento"
    with pytest.raises(ValidationError):
        superus.atualizar_bm_mensal(bm_id, mensal(status="Outro qualquer"), [])


def test_bm_mensal_obrigatorios(ambiente):
    cc_id = superus.criar_centro_custo(CC)
    with pytest.raises(ValidationError) as e:
        superus.criar_bm_mensal(cc_id, {}, [])
    assert set(e.value.errors) == {
        "titulo", "mes_referencia", "tipo", "valor_bm", "status", "cidade", "numero_contrato", "anexos"
    }


# 3. BM semanal: criar e consultar (com edição e exclusão)
def test_bm_semanal(ambiente):
    cc_id = superus.criar_centro_custo(CC)
    s1 = superus.criar_bm_semanal(cc_id, semanal(), [arquivo()])
    superus.criar_bm_semanal(cc_id, semanal(semana="Semana 2"), [arquivo()])
    superus.criar_bm_semanal(cc_id, semanal(mes_referencia="Abril"), [arquivo()])

    assert len(superus.listar_bms_semanais(centro_custo_id=cc_id)) == 3
    assert len(superus.listar_bms_semanais(centro_custo_id=cc_id, mes="Março")) == 2
    assert len(superus.listar_bms_semanais(centro_custo_id=cc_id, mes="Março", semana="Semana 2")) == 1
    assert superus.obter_bm_semanal(s1).valor_bm == Decimal("2500.00")
    assert not hasattr(superus.obter_bm_semanal(s1), "status")

    superus.atualizar_bm_semanal(s1, semanal(valor_bm="3.000"), [])
    assert superus.obter_bm_semanal(s1).valor_bm == Decimal("3000")
    superus.excluir_bm_semanal(s1)
    assert len(superus.listar_bms_semanais(centro_custo_id=cc_id)) == 2


# 5. Filtros: CC (pelo ID), mês, status, PO parcial
def test_filtros_mensal_e_po_parcial(ambiente):
    cc1 = superus.criar_centro_custo(CC)
    cc2 = superus.criar_centro_custo({**CC, "titulo": "DEV-SUP-200"})
    superus.criar_bm_mensal(cc1, mensal(po="PO-4500-ABC"), [arquivo()])
    superus.criar_bm_mensal(cc1, mensal(po="X-9", mes_referencia="Abril"), [arquivo()])
    superus.criar_bm_mensal(cc2, mensal(po="po-4500-zzz", status="BM Aprovado pelo Cliente"), [arquivo()])

    assert len(superus.listar_bms_mensais(centro_custo_id=cc1)) == 2
    assert len(superus.listar_bms_mensais(centro_custo_id=cc1, mes="Abril")) == 1
    assert len(superus.listar_bms_mensais(status="BM Aprovado pelo Cliente")) == 1
    assert len(superus.listar_bms_mensais(po="4500")) == 2  # parcial, sem diferenciar caixa
    assert len(superus.listar_bms_mensais(po="abc")) == 1
    assert len(superus.listar_bms_mensais(po="%")) == 0  # curinga tratado como texto
    assert len(superus.listar_bms_mensais(po="  ")) == 3  # filtro vazio = sem filtro


def test_cc_com_mesmo_nome_nao_mistura_registros(ambiente):
    """O original filtrava pelo Título; aqui o vínculo é pelo ID."""
    cc1 = superus.criar_centro_custo(CC)
    cc2 = superus.criar_centro_custo({**CC, "titulo": "DEV-SUP-100-B"})
    superus.criar_bm_mensal(cc1, mensal(), [arquivo()])
    assert superus.listar_bms_mensais(centro_custo_id=cc2) == []


# Faturamento SUPERUS ADM
def test_faturamento_edita_campos_permitidos(ambiente):
    cc_id = superus.criar_centro_custo(CC)
    bm_id = superus.criar_bm_mensal(cc_id, mensal(), [arquivo()])
    superus.atualizar_faturamento(
        bm_id,
        status="BM Aprovado pelo Cliente",
        valor_liberado="9.000,00",
        valor_emitido="8.000,00",
        mes_referencia="Abril",
        frs="4500012345",
        po="PO-NOVO",
        novos_anexos=[arquivo("nf.pdf")],
    )
    bm = superus.obter_bm_mensal(bm_id)
    assert (bm.valor_liberado, bm.valor_emitido, bm.mes_referencia, bm.po) == (
        Decimal("9000.00"),
        Decimal("8000.00"),
        "Abril",
        "PO-NOVO",
    )
    assert bm.frs == Decimal("4500012345")
    # Valor aprovado e glosa não mudam no faturamento
    assert bm.valor_aprovado == Decimal("9850.00")
    assert bm.glosa == Decimal("100")
    assert len(bm.anexos) == 2


def test_faturamento_nao_cria_registro(ambiente):
    with pytest.raises(NotFoundError):
        superus.atualizar_faturamento(
            77, status="BM Aprovado pelo Cliente", valor_liberado="", valor_emitido="",
            mes_referencia="Março", frs="", po="", novos_anexos=[],
        )
    assert superus.listar_bms_mensais() == []


# Atualizar dados (SUPERUS ADM)
def test_atualizar_dados_cc(ambiente):
    cc_id = superus.criar_centro_custo(CC)
    superus.atualizar_dados_cc(cc_id, qtd_bms="3", cidade="Cidade DEV", numero_contrato="CT-9")
    cc = superus.obter_centro_custo(cc_id)
    assert (cc.qtd_bms, cc.cidade, cc.numero_contrato) == (Decimal("3"), "Cidade DEV", "CT-9")
    assert cc.titulo == "DEV-SUP-100"  # demais campos intactos


def test_atualizar_dados_nao_cria_cc(ambiente):
    with pytest.raises(NotFoundError):
        superus.atualizar_dados_cc(55, qtd_bms="1", cidade="", numero_contrato="")
    assert superus.listar_centros_custo() == []
