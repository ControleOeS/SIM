"""Tela inicial: seleção da área (ASAP, SUPERUS ou Administrativo)."""
import streamlit as st

from sim import access_admin
from sim.services import encerramento
from sim.ui import navegacao as nav
from sim.ui.common import mostrar_flash
from sim.ui.layout import cartao_area, paginas, topo
from sim.ui.tema import img_logo

P = paginas()

topo(["O&S Gestão", "Início"])
st.markdown(
    f'<div class="sim-boasvindas">{img_logo("OES", "")}'
    "<div><h1>Bem-vindo ao SIM</h1><p>Selecione a área que deseja acessar.</p></div></div>",
    unsafe_allow_html=True,
)
mostrar_flash()

pendentes_enc = encerramento.contar_pendentes()
if pendentes_enc:
    st.warning(f"Há {pendentes_enc} solicitação(ões) de encerramento de centro de custo aguardando aprovação.",
               icon=":material/event_available:")
    for chave_tela, rotulo in (("sup_enc", "Encerramentos Superus"), ("asap_enc", "Encerramentos ASAP")):
        if chave_tela in P:
            st.page_link(P[chave_tela], label=rotulo, icon=":material/event_available:")

if "controle_acesso" in P:
    pendentes = access_admin.contar_solicitacoes_pendentes()
    if pendentes:
        st.warning(f"Há {pendentes} solicitação(ões) de acesso aguardando aprovação.", icon=":material/how_to_reg:")
        st.page_link(P["controle_acesso"], label="Analisar solicitações", icon=":material/admin_panel_settings:")

DESTINOS = {
    "asap_eng": (P.get("asap_eng"), nav.MODULOS["asap_eng"].descricao, "Acessar ASAP", False),
    "sup_eng": (P.get("sup_eng"), nav.MODULOS["sup_eng"].descricao, "Acessar SUPERUS", False),
    "adm": (
        P.get("adm_selecao"),
        "Faturamento e planejamento administrativo das empresas autorizadas.",
        "Escolher empresa",
        True,
    ),
}

areas_visiveis = [
    (chave, identidade, titulo, DESTINOS[chave])
    for chave, identidade, titulo in nav.AREAS_INICIO
    if DESTINOS[chave][0] is not None
]
if areas_visiveis:
    colunas = st.columns(min(3, len(areas_visiveis)), gap="medium")
    for col, (_, identidade, titulo, destino_config) in zip(colunas, areas_visiveis):
        destino, descricao, rotulo, logo_quadrado = destino_config
        with col:
            cartao_area(identidade, titulo, descricao, destino, rotulo, logo_quadrado=logo_quadrado)
else:
    st.info("Sua conta ainda não recebeu acesso a nenhum centro de custo. Contate o Controle.")

with st.expander("Sobre este ambiente", icon=":material/info:"):
    st.markdown(
        """
- O acesso depende do perfil: Usuário de obras (só os centros liberados), Planejador (todas as obras),
  Faturamento (só a área administrativa), Controle e Controle Geral.
- Novas contas são pedidas na aba "Solicitar acesso" do login e só valem depois da aprovação do Controle.
- O sistema começa vazio: não há dados fictícios nem importação das listas SharePoint.
- Campos marcados com ⚠ usam opções provisórias (`config/opcoes.json`), a confirmar com as listas originais.
"""
    )
