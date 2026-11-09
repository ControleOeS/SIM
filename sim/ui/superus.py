"""Fluxo "Escolha seu Centro de Custos" -> "Confirme seu Centro de Custo" (SIM SUPERUS).

O CC confirmado é guardado pelo ID (não pelo Título) e compartilhado entre
BM Mensal, BM Semanal e Encerramento durante a sessão do navegador.
"""
from __future__ import annotations

import streamlit as st

from sim.errors import NotFoundError
from sim.models import SuperusCentroCusto
from sim.services import superus
from sim.ui import common as ui

K_ID = "superus_cc_id"
K_ETAPA = "superus_cc_etapa"  # "escolher" | "confirmar" | "ok"


def _limpar() -> None:
    st.session_state[K_ETAPA] = "escolher"
    st.session_state.pop(K_ID, None)


def centro_custo_confirmado(pagina_cadastro=None) -> SuperusCentroCusto:
    """Mostra o fluxo de seleção quando necessário; devolve o CC confirmado ou interrompe a tela."""
    etapa = st.session_state.get(K_ETAPA, "escolher")
    cc_id = st.session_state.get(K_ID)

    if etapa == "ok" and cc_id is not None:
        try:
            cc = superus.obter_centro_custo(cc_id)
        except NotFoundError:
            _limpar()
            st.warning("O centro de custo escolhido não existe mais. Escolha outro.")
            st.stop()
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([1.2, 1.6, 1.4, 1], vertical_alignment="center")
            c1.markdown(f"**Centro de Custo**  \n{cc.titulo}")
            c2.markdown(f"**Obra/Cliente**  \n{cc.obra_cliente}")
            c3.markdown(f"**Gestor**  \n{cc.gestor_obra}")
            if c4.button("Mudar centro de custo", width="stretch", icon=ui.ICONE["trocar"]):
                _limpar()
                st.rerun()
        return cc

    ccs = ui.carregar(superus.listar_centros_custo)
    if not ccs:
        st.warning("Nenhum centro de custo cadastrado na SUPERUS.")
        if pagina_cadastro is not None:
            st.page_link(pagina_cadastro, label="Ir para Cadastro Centro de Custo", icon=":material/sell:")
        st.stop()
    por_id = {c.id: c for c in ccs}

    if etapa == "confirmar" and cc_id in por_id:
        cc = por_id[cc_id]
        with st.container(border=True):
            st.subheader("Confirme seu Centro de Custo", anchor=False)
            st.markdown(
                f"**Centro de Custo:** {cc.titulo}  \n**Obra/Cliente:** {cc.obra_cliente}  \n"
                f"**Gestor:** {cc.gestor_obra}"
            )
            st.caption("Caso não apareçam as informações, volte e escolha seu Centro de Custo.")
            b1, b2, _ = st.columns([1, 1, 3])
            if b1.button("OK", type="primary", width="stretch", icon=ui.ICONE["ok"]):
                st.session_state[K_ETAPA] = "ok"
                st.rerun()
            if b2.button("Voltar", width="stretch", icon=ui.ICONE["voltar"]):
                _limpar()
                st.rerun()
        st.stop()

    with st.container(border=True):
        st.subheader("Escolha seu Centro de Custos", anchor=False)
        st.caption("Lista em ordem crescente de código. Digite para buscar.")
        escolha = st.selectbox("Centro de custo", list(por_id), index=None, placeholder="Selecione",
                               format_func=lambda i: por_id[i].titulo)
        if st.button("OK", type="primary", disabled=escolha is None, icon=ui.ICONE["ok"]):
            st.session_state[K_ID] = escolha
            st.session_state[K_ETAPA] = "confirmar"
            st.rerun()
    st.stop()
