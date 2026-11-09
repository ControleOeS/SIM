"""Telas de encerramento de centro de custo (todas as coligadas) e a coluna Ativo do cadastro."""
from __future__ import annotations

from typing import Sequence

import pandas as pd
import streamlit as st

from sim.formatters import formatar_data_hora
from sim.services import asap, encerramento, superus
from sim.ui import common as ui

_LISTAR_CCS = {"ASAP": asap.listar_centros_custo, "SUPERUS": superus.listar_centros_custo}
_ROTULOS = {"justificativa": "Justificativa", "parecer": "Parecer", "centro_custo": "Centro de custo",
            "solicitacao": "Solicitação"}
_SITUACAO = {
    encerramento.PENDENTE: "Aguardando aprovação",
    encerramento.APROVADA: "Aprovada",
    encerramento.RECUSADA: "Recusada",
}


def _rotulo_cc(cc) -> str:
    detalhe = getattr(cc, "obra_cliente", None) or getattr(cc, "cliente", "")
    estado = "" if cc.ativo else " · ENCERRADO"
    return f"{cc.titulo} — {detalhe}{estado}"


def _nome(usuario) -> str:
    return usuario.nome if usuario is not None else "—"


def tela_encerramento(empresa: str, ns: str) -> None:
    ccs = ui.carregar(_LISTAR_CCS[empresa])
    decide = encerramento.pode_decidir()
    st.info(
        "Encerrar um centro de custo o deixa **inativo**: ele não aceita novos BMs (os já lançados continuam "
        "editáveis). Qualquer pessoa com acesso ao centro pode **solicitar** o encerramento, com justificativa; "
        "a decisão é do **Controle** ou do **Controle Geral**, que também podem reativá-lo."
    )
    if decide:
        _pendentes(empresa, ns)
        st.divider()

    st.subheader("Centro de custo", anchor=False)
    if not ccs:
        st.caption("Nenhum centro de custo disponível para você nesta coligada.")
        return
    por_id = {c.id: c for c in ccs}
    cc_id = st.selectbox("Centro de custo", list(por_id), format_func=lambda i: _rotulo_cc(por_id[i]),
                         index=None, placeholder="Selecione", key=f"{ns}-cc")  # mantém a escolha após gravar
    if cc_id is not None:
        _acoes_do_centro(empresa, ns, por_id[cc_id], decide)

    with st.expander("Histórico de encerramentos"):
        historico = ui.carregar(encerramento.listar, empresa)
        if not historico:
            st.caption("Nenhum registro ainda.")
        else:
            st.dataframe(
                [
                    {
                        "Data": formatar_data_hora(r.criado_em),
                        "Centro de Custo": r.centro_custo.titulo if r.centro_custo else "—",
                        "Ação": "Encerrar" if r.acao == encerramento.ENCERRAR else "Reativar",
                        "Situação": _SITUACAO[r.status],
                        "Justificativa": r.justificativa or "",
                        "Solicitante": _nome(r.solicitante),
                        "Decidido por": _nome(r.decidido_por),
                        "Parecer": r.parecer or "",
                    }
                    for r in historico
                ],
                hide_index=True,
                width="stretch",
            )


def _acoes_do_centro(empresa: str, ns: str, cc, decide: bool) -> None:
    ui.resumo_erros(ns, _ROTULOS)
    if not cc.ativo:
        st.warning(f"**{cc.titulo}** está encerrado e não aceita novos BMs.", icon=":material/block:")
        if decide:
            with ui.formulario():
                st.markdown("**Reativar centro de custo**")
                motivo = st.text_area("Justificativa (opcional)", key=ui.chave(ns, "motivo_reativar", cc.id))
                if st.button("Reativar", type="primary", icon=":material/restart_alt:"):
                    ui.executar(ns, lambda: encerramento.reativar(empresa, cc.id, motivo),
                                f"Centro de custo {cc.titulo} reativado.")
        return

    pendentes = ui.carregar(encerramento.listar, empresa, status=encerramento.PENDENTE, cc_id=cc.id)
    if pendentes and not decide:
        p = pendentes[0]
        st.info(
            f"Já existe uma solicitação de encerramento de **{cc.titulo}**, feita por {_nome(p.solicitante)} em "
            f"{formatar_data_hora(p.criado_em)}, aguardando aprovação.",
            icon=":material/hourglass_top:",
        )
        return

    titulo = "Encerrar centro de custo" if decide else "Solicitar encerramento"
    with ui.formulario():
        st.markdown(f"**{titulo}** · {cc.titulo}")
        justificativa = st.text_area(
            "Justificativa do encerramento da cobrança *", key=ui.chave(ns, "justificativa", cc.id),
            placeholder="Explique por que a cobrança deste centro de custo deve ser encerrada.",
        )
        ui.erro_campo(ns, "justificativa")
        enviar = st.button(
            "Encerrar agora" if decide else "Enviar solicitação", type="primary", icon=":material/event_available:"
        )
    if enviar:
        if decide:
            ui.executar(ns, lambda: encerramento.encerrar(empresa, cc.id, justificativa),
                        f"Centro de custo {cc.titulo} encerrado.")
        else:
            ui.executar(ns, lambda: encerramento.solicitar_encerramento(empresa, cc.id, justificativa),
                        "Solicitação enviada. O Controle vai analisar.")


def _pendentes(empresa: str, ns: str) -> None:
    st.subheader("Solicitações aguardando aprovação", anchor=False)
    pendentes = ui.carregar(encerramento.listar, empresa, status=encerramento.PENDENTE)
    if not pendentes:
        st.caption("Nenhuma solicitação pendente nesta coligada.")
        return
    for p in pendentes:
        with st.container(border=True):
            st.markdown(
                f"**{p.centro_custo.titulo}** · pedido por {_nome(p.solicitante)} em {formatar_data_hora(p.criado_em)}"
            )
            st.markdown("**Justificativa**")
            st.code(p.justificativa or "", language=None, wrap_lines=True)
            parecer = st.text_area("Parecer", key=ui.chave(ns, "parecer", p.id),
                                   placeholder="Opcional para aprovar; obrigatório para recusar.")
            c1, c2 = st.columns(2)
            if c1.button("Aprovar encerramento", type="primary", key=ui.chave(ns, "aprovar", p.id)):
                ui.executar(ns, lambda: encerramento.aprovar_solicitacao(p.id, parecer),
                            f"Encerramento de {p.centro_custo.titulo} aprovado.")
            if c2.button("Recusar", key=ui.chave(ns, "recusar", p.id)):
                ui.executar(ns, lambda: encerramento.recusar_solicitacao(p.id, parecer), "Solicitação recusada.")


# ------------------------------------------------- cadastro: coluna Ativo ----


def tabela_centros(ns: str, empresa: str, ccs: Sequence, linhas: list[dict]) -> None:
    """Tabela do cadastro com o checkbox Ativo, editável só por quem pode encerrar/reativar.

    Desmarcar pede justificativa (obrigatória) antes de gravar; marcar reativa o centro.
    """
    if not linhas:
        ui.tabela(ns, linhas, selecionavel=False)
        return
    df = pd.DataFrame([{"Ativo": cc.ativo, **linha} for cc, linha in zip(ccs, linhas)])
    coluna_ativo = st.column_config.CheckboxColumn(
        "Ativo", help="Desmarcado = centro de custo encerrado (não aceita novos BMs)."
    )
    if not encerramento.pode_decidir():
        st.dataframe(df, hide_index=True, width="stretch", column_config={"Ativo": coluna_ativo})
        return

    editado = st.data_editor(
        df, hide_index=True, width="stretch", key=ui.chave(ns, "ativos"),
        column_config={"Ativo": coluna_ativo}, disabled=[c for c in df.columns if c != "Ativo"],
    )
    mudancas = [
        (cc, bool(novo)) for cc, novo in zip(ccs, editado["Ativo"].tolist()) if bool(novo) != cc.ativo
    ]
    if not mudancas:
        return
    with st.container(border=True):
        st.markdown("**Confirmar alteração de status**")
        for cc, ativo in mudancas:
            st.markdown(f"- {cc.titulo}: {'**reativar**' if ativo else '**encerrar** (desativar)'}")
        desativando = any(not ativo for _, ativo in mudancas)
        justificativa = st.text_area(
            "Justificativa *" if desativando else "Justificativa (opcional)", key=ui.chave(ns, "just_ativo"),
            placeholder="Obrigatória para encerrar: por que a cobrança deve ser encerrada?",
        )
        c1, c2 = st.columns(2)
        if c1.button("Confirmar", type="primary", key=ui.chave(ns, "confirmar_ativo")):
            ui.executar(
                ns,
                lambda: [encerramento.definir_ativo(empresa, cc.id, ativo, justificativa) for cc, ativo in mudancas],
                "Status dos centros de custo atualizado.",
            )
        if c2.button("Descartar", key=ui.chave(ns, "descartar_ativo")):
            ui.reiniciar(ns)
            st.rerun()
        if ui.erros(ns):
            st.error(" ".join(ui.erros(ns).values()), icon=":material/error:")
