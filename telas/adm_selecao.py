"""Administrativo: seleção da empresa (ASAP ADM ou SUPERUS ADM)."""
import streamlit as st

from sim.ui import navegacao as nav
from sim.ui.common import ICONE
from sim.ui.layout import cartao_area, paginas, topo

P = paginas()

topo(["O&S Gestão", "Administrativo"])
st.title("Administrativo", anchor=False)
st.markdown('<div class="sim-sub">Escolha a empresa para abrir o faturamento e o planejamento.</div>',
            unsafe_allow_html=True)

opcoes_visiveis = [chave for chave in nav.OPCOES_ADM if nav.MODULOS[chave].entrada.chave in P]
colunas = st.columns(max(1, len(opcoes_visiveis)), gap="medium")
for col, chave in zip(colunas, opcoes_visiveis):
    m = nav.MODULOS[chave]
    with col:
        cartao_area(m.empresa, m.titulo, m.descricao, P[m.entrada.chave], f"Abrir {m.titulo}")

st.page_link(P["inicio"], label="Voltar à página inicial", icon=ICONE["voltar"])
