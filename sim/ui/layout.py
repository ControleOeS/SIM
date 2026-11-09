"""Componentes de layout: tema, cabeçalho, barra lateral, cartões de área e estados vazios.

A O&S Gestão é a identidade principal (cabeçalho, barra lateral, início); ASAP e
Superus aparecem como identidade secundária conforme o módulo aberto.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from sim.ui import navegacao as nav
from sim.ui.tema import CSS, IDENTIDADES, NOME_SISTEMA, caminho_logo, img_logo


def aplicar_tema() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def paginas() -> dict:
    return st.session_state["_paginas"]


# ------------------------------------------------------------ cabeçalho ----


def topo(itens_migalhas: list[str], coligada: str | None = None) -> None:
    """Faixa superior: O&S + nome do sistema + migalhas; logotipo da coligada à direita."""
    acento = IDENTIDADES[coligada].cor_detalhe if coligada else IDENTIDADES["OES"].cor_detalhe
    partes = [escape(i) for i in itens_migalhas]
    if partes:
        partes[-1] = f"<b>{partes[-1]}</b>"
    migalhas = "<span>›</span>".join(partes)
    direita = img_logo(coligada, "sim-topo__coligada") if coligada else ""
    st.markdown(
        f'<div class="sim-topo" style="--sim-acento:{acento}">'
        f'<div class="sim-topo__marca">{img_logo("OES", "sim-topo__oes")}'
        f'<div><div class="sim-topo__sistema">{NOME_SISTEMA}</div>'
        f'<nav class="sim-migalhas" aria-label="Você está em">{migalhas}</nav></div></div>'
        f"{direita}</div>",
        unsafe_allow_html=True,
    )


def titulo_tela(empresa: str, tipo: str, titulo: str, subtitulo: str = "") -> None:
    ident = IDENTIDADES[empresa]
    area = nav.nome_tipo(empresa, tipo)
    chip_area = f'<span class="sim-chip">{area}</span>' if area else ""
    st.markdown(
        f'<div class="sim-chips" style="--sim-cor:{ident.cor_escura};--sim-cor-clara:{ident.cor_clara}">'
        f'<span class="sim-chip">{escape(nav.NOME_EMPRESA[empresa])}</span>'
        f"{chip_area}</div>",
        unsafe_allow_html=True,
    )
    st.title(titulo, anchor=False)
    if subtitulo:
        st.markdown(f'<div class="sim-sub">{escape(subtitulo)}</div>', unsafe_allow_html=True)


# ------------------------------------------------------- barra lateral ----


def barra_lateral(modulo: nav.Modulo | None, pagina_atual: str, principal) -> None:
    from sim.ui.authentication import sair

    P = paginas()
    st.logo(str(caminho_logo("OES")), size="large", icon_image=str(caminho_logo("OES")))
    with st.sidebar:
        st.page_link(P["inicio"], label="Selecionar área", icon=":material/apps:")
        st.caption(f"Conectado: {principal.nome}")
        if "controle_acesso" in P:
            st.page_link(
                P["controle_acesso"],
                label="Controle de acesso",
                icon=":material/admin_panel_settings:",
            )
        if modulo is None:
            if pagina_atual == "adm_selecao":
                st.caption("Escolha a empresa para abrir o módulo administrativo.")
        else:
            if modulo.tipo == "ADM":
                st.page_link(P["adm_selecao"], label="Trocar empresa (Administrativo)", icon=":material/swap_horiz:")
            st.markdown(
                f'<div class="sim-lateral-area">{img_logo(modulo.empresa, "")}'
                f"<div><b>{escape(nav.NOME_EMPRESA[modulo.empresa])}</b>{nav.nome_tipo(modulo.empresa, modulo.tipo)}</div></div>",
                unsafe_allow_html=True,
            )
            st.page_link(P[modulo.entrada.chave], label=modulo.entrada.titulo, icon=modulo.entrada.icone)
            for t in modulo.telas:
                if t.chave in P:
                    st.page_link(P[t.chave], label=t.titulo, icon=t.icone)
        from sim.ui.authentication import TROCA_SENHA_ABERTA, dialogo_trocar_senha

        from sim.auth import principal_atual

        principal = principal_atual()
        if principal.administrador_acessos:  # só administradores trocam a senha por aqui
            if st.button("Trocar senha", key="sim-trocar-senha", width="stretch", icon=":material/key:"):
                st.session_state[TROCA_SENHA_ABERTA] = True
            if st.session_state.get(TROCA_SENHA_ABERTA):
                dialogo_trocar_senha(principal)
        if st.button("Sair", key="sim-sair", width="stretch"):
            sair()
        st.divider()
        st.markdown(
            '<div class="sim-rodape"><b>O&amp;S Gestão</b> · SIM<br>'
            "Acesso restrito por conta e centro de custo.</div>",
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------- cartões ----


def cartao_area(codigo_identidade: str, titulo: str, descricao: str, destino, rotulo: str,
                logo_quadrado: bool = False) -> None:
    ident = IDENTIDADES[codigo_identidade]
    classe = "sim-cartao__logo sim-cartao__logo--oes" if logo_quadrado else "sim-cartao__logo"
    with st.container(border=True, height="stretch"):
        st.markdown(
            f'<div class="sim-cartao" style="--sim-cor-detalhe:{ident.cor_detalhe}">'
            f"{img_logo(codigo_identidade, classe)}"
            f'<div class="sim-cartao__faixa"></div>'
            f'<div class="sim-cartao__titulo">{escape(titulo)}</div>'
            f'<div class="sim-cartao__texto">{escape(descricao)}</div></div>',
            unsafe_allow_html=True,
        )
        st.page_link(destino, label=rotulo, icon=":material/arrow_forward:", width="stretch")


def estado_vazio(titulo: str, texto: str = "") -> None:
    st.markdown(f'<div class="sim-vazio"><b>{escape(titulo)}</b>{escape(texto)}</div>', unsafe_allow_html=True)


def secao(titulo: str) -> None:
    """Rótulo de grupo de campos dentro de formulários."""
    st.markdown(f'<div class="sim-secao">{escape(titulo)}</div>', unsafe_allow_html=True)


# ------------------------------------------------- página de módulo ----


def pagina_modulo(chave_modulo: str) -> None:
    """Tela inicial de um módulo (equivale à 'Tela Inicial' de cada Power App)."""
    from sim.ui.common import cabecalho

    m = nav.MODULOS[chave_modulo]
    P = paginas()
    telas = [t for t in m.telas if t.chave in P]  # só as telas liberadas para o perfil
    cabecalho(m.empresa, m.tipo, m.titulo, m.descricao, tela=None)
    st.markdown("Escolha a tela:")
    colunas = st.columns(min(3, len(telas)) if len(telas) > 1 else 2)
    for i, t in enumerate(telas):
        with colunas[i % len(colunas)]:
            with st.container(border=True, height="stretch"):
                st.page_link(P[t.chave], label=t.titulo, icon=t.icone, width="stretch")
                if t.resumo:
                    st.markdown(f'<div class="sim-atalho__texto">{escape(t.resumo)}</div>', unsafe_allow_html=True)
