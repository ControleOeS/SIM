"""Regras do SIM ASAP — Engenharia e SIM ASAP — Administrativo.

Rastreabilidade (relatório "SIM ASAP — Auditoria e Mapeamento Funcional"):
RN-01 lista por ID decrescente; RN-03/P-01 CC do próprio registro na edição;
RN-05 obrigatórios do BM; RN-07 data de aprovação; RN-11/RN-12 cadastro de CC.
"""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sim.auth import escopos_centros, exigir_area_adm, exigir_area_obras, exigir_centro, exigir_controlador
from sim.errors import NotFoundError, ValidationError
from sim.formatters import normalizar_chave
from sim.models import AsapBM, AsapCentroCusto, utcnow
from sim.options import STATUS_APROVADO_CLIENTE, STATUS_FATURADO_TOTAL, opcoes
from sim.repositories.asap import AsapBMRepository, AsapCentroCustoRepository
from sim.repositories.base import EmpresaRepository
from sim.services.common import (
    Validador,
    conferir_versao,
    contar_anexos_finais,
    leitura,
    transacao,
    validar_arquivos,
)
from sim.services.encerramento import verificar_cc_ativo
from sim.storage import ArquivoNovo

EMPRESA = "ASAP"


def _pasta_anexos(bm_id: int) -> str:
    return f"asap/bm/{bm_id}"


# ------------------------------------------------------ regras puras ----


def aplicar_data_aprovacao(bm: AsapBM, agora: datetime | None = None) -> bool:
    """RN-07 (Form1.OnSuccess): status 'BM Aprovado pelo Cliente' sem data -> data/hora atual.

    Nunca sobrescreve uma data existente. Retorna True quando preencheu.
    """
    if bm.status == STATUS_APROVADO_CLIENTE and bm.data_aprovacao_cliente is None:
        bm.data_aprovacao_cliente = agora or utcnow()
        return True
    return False


def status_permitidos_faturamento(status_atual: str | None) -> list[str]:
    """SIM ASAP ADM: Items = ["Faturado Total", varItemParaEditar.Status.Value], sem duplicar."""
    opcoes_ = [STATUS_FATURADO_TOTAL]
    if status_atual and status_atual not in opcoes_:
        opcoes_.append(status_atual)
    return opcoes_


# ------------------------------------------------- centros de custo ----


def _validar_cc(dados: dict) -> dict:
    v = Validador()
    v.texto("titulo", dados.get("titulo"), obrigatorio=True)
    v.texto("cliente", dados.get("cliente"), obrigatorio=True)
    v.dia_do_mes("inicio_medicao", dados.get("inicio_medicao"), obrigatorio=True)
    v.dia_do_mes("fim_medicao", dados.get("fim_medicao"), obrigatorio=True)
    v.texto("email", dados.get("email"), obrigatorio=True, max_len=None)  # original não valida formato
    v.texto("periodo", dados.get("periodo"))
    return v.verificar()


def listar_centros_custo() -> Sequence[AsapCentroCusto]:
    permitidos = escopos_centros(EMPRESA)
    with leitura() as s:
        centros = AsapCentroCustoRepository(s).listar()
        return centros if permitidos is None else [c for c in centros if c.id in permitidos]


def criar_centro_custo(dados: dict) -> int:
    """Cadastro (RN-11/RN-12). Melhoria documentada: bloqueia Título duplicado."""
    exigir_controlador()
    valores = _validar_cc(dados)
    chave = normalizar_chave(valores["titulo"])
    with transacao("asap.criar_centro_custo") as tx:
        repo = AsapCentroCustoRepository(tx.session)
        if repo.por_chave(chave):
            raise ValidationError({"titulo": "Já existe um centro de custo com este título."})
        empresa = EmpresaRepository(tx.session).por_codigo(EMPRESA)
        cc = repo.add(AsapCentroCusto(empresa_id=empresa.id, titulo_chave=chave, **valores))
        return cc.id


def atualizar_centro_custo(cc_id: int, dados: dict, *, versao: int | None = None) -> None:
    """Disponível na camada de serviço; a tela Cadastro original só inclui (RN-12)."""
    exigir_centro(EMPRESA, cc_id, escrita=True)
    valores = _validar_cc(dados)
    chave = normalizar_chave(valores["titulo"])
    with transacao("asap.atualizar_centro_custo") as tx:
        repo = AsapCentroCustoRepository(tx.session)
        cc = repo.get(cc_id)
        if cc is None:
            raise NotFoundError("Centro de custo não encontrado.")
        conferir_versao(cc, versao)
        outro = repo.por_chave(chave)
        if outro and outro.id != cc_id:
            raise ValidationError({"titulo": "Já existe um centro de custo com este título."})
        for k, val in valores.items():
            setattr(cc, k, val)
        cc.titulo_chave = chave


def excluir_centro_custo(cc_id: int, *, versao: int | None = None) -> None:
    exigir_centro(EMPRESA, cc_id, escrita=True)
    with transacao("asap.excluir_centro_custo") as tx:
        repo = AsapCentroCustoRepository(tx.session)
        cc = repo.get(cc_id)
        if cc is None:
            raise NotFoundError("Centro de custo não encontrado.")
        conferir_versao(cc, versao)
        if repo.possui_bms(cc_id):
            raise ValidationError({"centro_custo": "Este centro de custo tem BMs vinculados e não pode ser excluído."})
        repo.delete(cc)


# --------------------------------------------------------- BM Mensal ----


def _validar_bm(dados: dict, atual: AsapBM | None) -> dict:
    v = Validador()
    if not dados.get("centro_custo_id"):
        v.erro("centro_custo_id", "Escolha o centro de custo.")
    v.valores["centro_custo_id"] = dados.get("centro_custo_id")
    v.texto("titulo", dados.get("titulo"), obrigatorio=True)
    v.escolha("ano", dados.get("ano"), opcoes("asap.ano").com_valor_atual(atual and atual.ano), obrigatorio=True)
    v.escolha(
        "mes_referencia",
        dados.get("mes_referencia"),
        opcoes("asap.mes_referencia").com_valor_atual(atual and atual.mes_referencia),
        obrigatorio=True,
    )
    v.escolha(
        "status", dados.get("status"), opcoes("asap.status").com_valor_atual(atual and atual.status), obrigatorio=True
    )
    v.moeda("valor_bm", dados.get("valor_bm"), obrigatorio=True)
    v.moeda("valor_aprovado", dados.get("valor_aprovado"), obrigatorio=True)
    v.moeda("glosa", dados.get("glosa"))
    v.texto("observacoes", dados.get("observacoes"), max_len=None)
    return v


def listar_bms(*, centro_custo_id: int | None = None, mes: str | None = None, status: str | None = None):
    permitidos = escopos_centros(EMPRESA)
    if centro_custo_id is not None:
        exigir_centro(EMPRESA, centro_custo_id)
    with leitura() as s:
        return AsapBMRepository(s).listar(
            centro_custo_id=centro_custo_id,
            centro_custo_ids=permitidos,
            mes=mes,
            status=status,
        )


def obter_bm(bm_id: int) -> AsapBM:
    with leitura() as s:
        bm = AsapBMRepository(s).get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM não encontrado. Ele pode ter sido excluído.")
        exigir_centro(EMPRESA, bm.centro_custo_id)
        return bm


def criar_bm(dados: dict, anexos: list[ArquivoNovo]) -> int:
    exigir_area_obras()
    v = _validar_bm(dados, None)
    if not anexos:
        v.erro("anexos", "Adicione pelo menos um anexo.")
    valores = v.verificar()
    exigir_centro(EMPRESA, valores["centro_custo_id"], escrita=True)
    validar_arquivos(anexos)
    with transacao("asap.criar_bm") as tx:
        cc = AsapCentroCustoRepository(tx.session).get(valores["centro_custo_id"])
        if cc is None:
            raise ValidationError({"centro_custo_id": "Centro de custo inexistente."})
        verificar_cc_ativo(cc)
        bm = AsapBMRepository(tx.session).add(AsapBM(**valores))
        aplicar_data_aprovacao(bm)
        tx.anexar(_pasta_anexos(bm.id), anexos, asap_bm_id=bm.id)
        return bm.id


def atualizar_bm(
    bm_id: int,
    dados: dict,
    novos_anexos: list[ArquivoNovo],
    remover_anexo_ids: list[int] | None = None,
    *,
    versao: int | None = None,
) -> None:
    """Edição: exige um BM existente e nunca cria um novo.

    O centro de custo enviado é o do formulário de edição, que começa com o CC do
    próprio registro (correção P-01); o serviço não usa o CC escolhido na entrada.
    """
    exigir_area_obras()
    remover_anexo_ids = remover_anexo_ids or []
    validar_arquivos(novos_anexos)
    with transacao("asap.atualizar_bm") as tx:
        repo = AsapBMRepository(tx.session)
        bm = repo.get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM não encontrado. Ele pode ter sido excluído; nada foi gravado.")
        exigir_centro(EMPRESA, bm.centro_custo_id, escrita=True)
        conferir_versao(bm, versao)
        v = _validar_bm(dados, bm)
        if contar_anexos_finais(bm.anexos, remover_anexo_ids, novos_anexos) == 0:
            v.erro("anexos", "O BM precisa manter pelo menos um anexo.")
        valores = v.verificar()
        exigir_centro(EMPRESA, valores["centro_custo_id"], escrita=True)
        destino = AsapCentroCustoRepository(tx.session).get(valores["centro_custo_id"])
        if destino is None:
            raise ValidationError({"centro_custo_id": "Centro de custo inexistente."})
        if destino.id != bm.centro_custo_id:  # mover um BM conta como lançamento novo no CC de destino
            verificar_cc_ativo(destino)
        for k, val in valores.items():
            setattr(bm, k, val)
        aplicar_data_aprovacao(bm)
        tx.remover_anexos(a for a in bm.anexos if a.id in set(remover_anexo_ids))
        tx.anexar(_pasta_anexos(bm.id), novos_anexos, asap_bm_id=bm.id)


def excluir_bm(bm_id: int, *, versao: int | None = None) -> None:
    exigir_area_obras()
    with transacao("asap.excluir_bm") as tx:
        repo = AsapBMRepository(tx.session)
        bm = repo.get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM não encontrado. Ele pode já ter sido excluído.")
        exigir_centro(EMPRESA, bm.centro_custo_id, escrita=True)
        conferir_versao(bm, versao)
        tx.marcar_para_remover(a.caminho_relativo for a in bm.anexos)
        repo.delete(bm)


# ------------------------------------------------ Faturamento (ADM) ----


def opcoes_filtro_faturamento() -> dict:
    exigir_area_adm()
    permitidos = escopos_centros(EMPRESA)
    with leitura() as s:
        repo = AsapBMRepository(s)
        return {
            "meses": list(opcoes("asap.mes_referencia").valores),
            "status": repo.status_distintos(permitidos),
            "centros": repo.centros_com_bm(permitidos),
        }


def atualizar_faturamento(
    bm_id: int,
    *,
    valor_emitido: object,
    status: str,
    novos_anexos: list[ArquivoNovo],
    remover_anexo_ids: list[int] | None = None,
    versao: int | None = None,
) -> None:
    """SIM ASAP ADM: altera só Valor Emitido, Status e Anexos de um BM existente."""
    exigir_area_adm()
    remover_anexo_ids = remover_anexo_ids or []
    validar_arquivos(novos_anexos)
    with transacao("asap.atualizar_faturamento") as tx:
        bm = AsapBMRepository(tx.session).get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM não encontrado. Ele pode ter sido excluído; nada foi gravado.")
        exigir_centro(EMPRESA, bm.centro_custo_id, escrita=True)
        conferir_versao(bm, versao)
        v = Validador()
        v.moeda("valor_emitido", valor_emitido)
        v.escolha("status", status, status_permitidos_faturamento(bm.status), obrigatorio=True)
        valores = v.verificar()
        bm.valor_emitido = valores["valor_emitido"]
        bm.status = valores["status"]
        tx.remover_anexos(a for a in bm.anexos if a.id in set(remover_anexo_ids))
        tx.anexar(_pasta_anexos(bm.id), novos_anexos, asap_bm_id=bm.id)
