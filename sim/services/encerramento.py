"""Encerramento (desativação) e reativação de centros de custo, para todas as coligadas.

Regras (decisão do responsável em 2026-10-26):
- Centro de custo encerrado fica inativo e não aceita novos BMs; os BMs já lançados continuam editáveis.
- Quem tem acesso ao centro de custo pode **solicitar** o encerramento, com justificativa obrigatória.
- Quem decide (aprova/recusa pedidos, encerra diretamente e reativa) são os perfis Controle e
  Controle Geral (`Principal.controlador`). Planejador e usuário de obras só solicitam.
- Tudo fica registrado em `encerramentos_cc`; ações diretas entram já aprovadas.
- Na SUPERUS, os campos originais EncerramentoManual/Motivo Encerramento acompanham o status.
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from sim.auth import escopos_centros, exigir_area_obras, exigir_centro, exigir_controlador, principal_atual
from sim.errors import NotFoundError, ValidationError
from sim.models import (
    AsapCentroCusto,
    EncerramentoCentroCusto,
    Empresa,
    SuperusCentroCusto,
    utcnow,
)
from sim.services.common import leitura, transacao

PENDENTE = "pendente"
APROVADA = "aprovada"
RECUSADA = "recusada"
ENCERRAR = "encerrar"
REATIVAR = "reativar"
_MAX_TEXTO = 2000

_MODELOS = {"ASAP": AsapCentroCusto, "SUPERUS": SuperusCentroCusto}
_COLUNA_CC = {"ASAP": "asap_cc_id", "SUPERUS": "superus_cc_id"}
MENSAGEM_CC_INATIVO = "Este centro de custo está encerrado e não aceita novos BMs."


def pode_decidir() -> bool:
    return principal_atual().controlador


def _modelo(empresa: str):
    try:
        return _MODELOS[empresa]
    except KeyError:
        raise ValidationError({"empresa": "Empresa inválida."}) from None


def _texto(campo: str, valor: object, *, obrigatorio: bool, mensagem: str) -> str | None:
    texto = ("" if valor is None else str(valor)).strip()
    if obrigatorio and not texto:
        raise ValidationError({campo: mensagem})
    if len(texto) > _MAX_TEXTO:
        raise ValidationError({campo: f"Use no máximo {_MAX_TEXTO} caracteres."})
    return texto or None


def _centro(session, empresa: str, cc_id: int):
    cc = session.get(_modelo(empresa), cc_id)
    if cc is None:
        raise NotFoundError("Centro de custo não encontrado.")
    return cc


def _filtro_cc(empresa: str, cc_id: int):
    return getattr(EncerramentoCentroCusto, _COLUNA_CC[empresa]) == cc_id


def _novo_registro(session, empresa: str, cc_id: int, **campos) -> EncerramentoCentroCusto:
    empresa_id = session.scalar(select(Empresa.id).where(Empresa.codigo == empresa))
    registro = EncerramentoCentroCusto(empresa_id=empresa_id, **{_COLUNA_CC[empresa]: cc_id}, **campos)
    session.add(registro)
    return registro


def _aplicar_status(empresa: str, cc, ativo: bool, motivo: str | None) -> None:
    cc.ativo = ativo
    if empresa == "SUPERUS":
        cc.encerramento_manual = "Não" if ativo else "Sim"
        if not ativo:
            cc.motivo_encerramento = motivo


def verificar_cc_ativo(cc) -> None:
    """Usada pelos serviços de BM antes de criar um BM (ou mover um BM para outro CC)."""
    if not cc.ativo:
        raise ValidationError({"centro_custo_id": MENSAGEM_CC_INATIVO})


# ------------------------------------------------------------- pedidos ----


def solicitar_encerramento(empresa: str, cc_id: int, justificativa: object) -> int:
    exigir_area_obras()
    exigir_centro(empresa, cc_id, escrita=True)
    texto = _texto("justificativa", justificativa, obrigatorio=True,
                   mensagem="Explique por que a cobrança deste centro de custo deve ser encerrada.")
    with transacao("encerramento.solicitar") as tx:
        cc = _centro(tx.session, empresa, cc_id)
        if not cc.ativo:
            raise ValidationError({"centro_custo": "Este centro de custo já está encerrado."})
        if tx.session.scalar(
            select(EncerramentoCentroCusto.id).where(
                _filtro_cc(empresa, cc_id), EncerramentoCentroCusto.status == PENDENTE
            )
        ):
            raise ValidationError({"centro_custo": "Já existe uma solicitação de encerramento aguardando aprovação."})
        registro = _novo_registro(
            tx.session, empresa, cc_id, acao=ENCERRAR, status=PENDENTE,
            justificativa=texto, solicitante_id=principal_atual().id,
        )
        try:
            tx.session.flush()
        except IntegrityError as exc:  # outro pedido gravado ao mesmo tempo (índice único de pendentes)
            raise ValidationError(
                {"centro_custo": "Já existe uma solicitação de encerramento aguardando aprovação."}
            ) from exc
        return registro.id


def _aprovador_id() -> int:
    exigir_controlador()
    return principal_atual().id


def aprovar_solicitacao(solicitacao_id: int, parecer: object = "") -> None:
    aprovador_id = _aprovador_id()
    texto = _texto("parecer", parecer, obrigatorio=False, mensagem="")
    with transacao("encerramento.aprovar") as tx:
        registro = _pendente(tx.session, solicitacao_id)
        empresa = "ASAP" if registro.asap_cc_id is not None else "SUPERUS"
        cc = _centro(tx.session, empresa, registro.asap_cc_id or registro.superus_cc_id)
        _aplicar_status(empresa, cc, False, registro.justificativa)
        registro.status, registro.parecer = APROVADA, texto
        registro.decidido_por_id, registro.decidido_em = aprovador_id, utcnow()


def recusar_solicitacao(solicitacao_id: int, parecer: object) -> None:
    aprovador_id = _aprovador_id()
    texto = _texto("parecer", parecer, obrigatorio=True, mensagem="Escreva o motivo da recusa no parecer.")
    with transacao("encerramento.recusar") as tx:
        registro = _pendente(tx.session, solicitacao_id)
        registro.status, registro.parecer = RECUSADA, texto
        registro.decidido_por_id, registro.decidido_em = aprovador_id, utcnow()


def _pendente(session, solicitacao_id: int) -> EncerramentoCentroCusto:
    registro = session.get(EncerramentoCentroCusto, solicitacao_id)
    if registro is None:
        raise NotFoundError("Solicitação não encontrada.")
    if registro.status != PENDENTE:
        raise ValidationError({"solicitacao": "Esta solicitação já foi decidida."})
    return registro


# ------------------------------------------------------ ações diretas ----


def encerrar(empresa: str, cc_id: int, justificativa: object) -> None:
    """Encerramento direto (formulário ou checkbox Ativo). Atende os pedidos pendentes do CC."""
    exigir_controlador()
    texto = _texto("justificativa", justificativa, obrigatorio=True,
                   mensagem="Informe a justificativa do encerramento.")
    agora, quem = utcnow(), principal_atual().id
    with transacao("encerramento.encerrar") as tx:
        cc = _centro(tx.session, empresa, cc_id)
        if not cc.ativo:
            raise ValidationError({"centro_custo": "Este centro de custo já está encerrado."})
        _aplicar_status(empresa, cc, False, texto)
        for pedido in tx.session.scalars(
            select(EncerramentoCentroCusto).where(
                _filtro_cc(empresa, cc_id), EncerramentoCentroCusto.status == PENDENTE
            )
        ):
            pedido.status, pedido.decidido_por_id, pedido.decidido_em = APROVADA, quem, agora
            pedido.parecer = "Atendida pelo encerramento direto do centro de custo."
        _novo_registro(
            tx.session, empresa, cc_id, acao=ENCERRAR, status=APROVADA, justificativa=texto,
            solicitante_id=quem, decidido_por_id=quem, decidido_em=agora,
        )


def reativar(empresa: str, cc_id: int, justificativa: object = "") -> None:
    exigir_controlador()
    texto = _texto("justificativa", justificativa, obrigatorio=False, mensagem="")
    agora, quem = utcnow(), principal_atual().id
    with transacao("encerramento.reativar") as tx:
        cc = _centro(tx.session, empresa, cc_id)
        if cc.ativo:
            raise ValidationError({"centro_custo": "Este centro de custo já está ativo."})
        _aplicar_status(empresa, cc, True, None)
        _novo_registro(
            tx.session, empresa, cc_id, acao=REATIVAR, status=APROVADA, justificativa=texto,
            solicitante_id=quem, decidido_por_id=quem, decidido_em=agora,
        )


def definir_ativo(empresa: str, cc_id: int, ativo: bool, justificativa: object = "") -> None:
    """Caminho do checkbox Ativo do cadastro."""
    if ativo:
        reativar(empresa, cc_id, justificativa)
    else:
        encerrar(empresa, cc_id, justificativa)


# ------------------------------------------------------------ consulta ----


def listar(empresa: str, *, status: str | None = None, cc_id: int | None = None) -> Sequence[EncerramentoCentroCusto]:
    """Pedidos e registros visíveis ao usuário (só dos centros de custo que ele acessa)."""
    _modelo(empresa)
    if cc_id is not None:
        exigir_centro(empresa, cc_id)
    permitidos = escopos_centros(empresa)
    coluna = getattr(EncerramentoCentroCusto, _COLUNA_CC[empresa])
    consulta = (
        select(EncerramentoCentroCusto)
        .where(coluna.is_not(None))
        .options(
            selectinload(EncerramentoCentroCusto.asap_centro_custo),
            selectinload(EncerramentoCentroCusto.superus_centro_custo),
            selectinload(EncerramentoCentroCusto.solicitante),
            selectinload(EncerramentoCentroCusto.decidido_por),
        )
    )
    if permitidos is not None:
        consulta = consulta.where(coluna.in_(permitidos or {-1}))
    if cc_id is not None:
        consulta = consulta.where(coluna == cc_id)
    if status is not None:
        consulta = consulta.where(EncerramentoCentroCusto.status == status)
    ordem = EncerramentoCentroCusto.criado_em.asc() if status == PENDENTE else EncerramentoCentroCusto.criado_em.desc()
    with leitura() as s:
        return list(s.scalars(consulta.order_by(ordem, EncerramentoCentroCusto.id)))


def contar_pendentes() -> int:
    """Pedidos aguardando decisão, nas duas empresas (só para quem decide)."""
    if not pode_decidir():
        return 0
    with leitura() as s:
        return s.scalar(
            select(func.count(EncerramentoCentroCusto.id)).where(EncerramentoCentroCusto.status == PENDENTE)
        )
