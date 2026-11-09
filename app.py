"""SIM — Sistema Integrado de Medições. Ponto de entrada do Streamlit.

Executar:  .venv\\Scripts\\python.exe -m streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path

from sim.recarga import descartar_modulos_alterados

# Antes de qualquer outro import do pacote: se o código mudou com o servidor aberto,
# descarta todos os módulos sim.* juntos para não misturar versões (ver sim/recarga.py).
descartar_modulos_alterados(Path(__file__).resolve().parent / "sim", "sim")

import streamlit as st  # noqa: E402
from PIL import Image  # noqa: E402

from sim.bootstrap import EsquemaDesatualizado, inicializar  # noqa: E402
from sim.auth import usando_principal  # noqa: E402
from sim.logging_setup import get_logger, nova_referencia  # noqa: E402
from sim.ui import navegacao as nav  # noqa: E402
from sim.ui.layout import aplicar_tema, barra_lateral  # noqa: E402
from sim.ui.tema import NOME_SISTEMA, caminho_logo  # noqa: E402
from sim.ui.authentication import usuario_autenticado  # noqa: E402

def _segredos_para_ambiente() -> None:
    """Na hospedagem (Streamlit Community Cloud) a configuração vem do painel "Secrets". O SIM lê tudo
    de variáveis de ambiente (sim.config), então copia as chaves de primeiro nível sem sobrescrever
    as que já existem. Localmente não há secrets.toml e a configuração vem do .env."""
    import os

    try:
        itens = dict(st.secrets)
    except Exception:  # sem secrets.toml
        return
    for chave, valor in itens.items():
        if isinstance(valor, (str, int, float, bool)):
            os.environ.setdefault(chave, str(valor))


_segredos_para_ambiente()
st.set_page_config(
    page_title=f"SIM — {NOME_SISTEMA}",
    page_icon=Image.open(caminho_logo("OES")),
    layout="wide",
)
aplicar_tema()


@st.cache_resource(show_spinner="Preparando o SIM…")
def _iniciar():
    return inicializar()


try:
    _iniciar()
except EsquemaDesatualizado as exc:
    st.error(str(exc))
    st.stop()
except Exception:
    get_logger("app").exception("Falha ao iniciar o SIM")
    st.error("Não foi possível abrir o banco de dados do SIM. Veja data/logs/sim.log para detalhes.")
    st.stop()


# Cadastro de CC só para os Controles (criar exige controlador). O Encerramento todos da área de
# obras veem, mas Planejador e usuário de obras só solicitam; a decisão fica com os Controles (no serviço).
TELAS_SO_CONTROLADOR = {"asap_cc", "sup_cc"}


def _telas_autorizadas(principal):
    """Telas por perfil (as mesmas regras valem nos serviços; aqui só se escondem as telas).

    - Área de obras (ASAP e SUPERUS): usuário de obras (só empresas com centro liberado), Planejador e Controles.
    - Área administrativa (ASAP ADM e SUPERUS ADM): Faturamento e Controles, nas duas coligadas.
    """
    empresas = {empresa for empresa, _ in principal.escopos}
    telas = [nav.INICIO]
    if principal.area_adm:
        telas.append(nav.SELECAO_ADM)
    for modulo in nav.MODULOS.values():
        if modulo.tipo == "ADM":
            if not principal.area_adm:
                continue
        elif not principal.area_obras or not (principal.ve_todas_obras or modulo.empresa in empresas):
            continue
        telas.append(modulo.entrada)
        telas.extend(t for t in modulo.telas if principal.controlador or t.chave not in TELAS_SO_CONTROLADOR)
    return telas


def _executar(principal) -> None:
    telas = _telas_autorizadas(principal)
    P = {
        t.chave: st.Page(
            t.arquivo,
            title=t.titulo,
            icon=t.icone,
            url_path=t.url or None,
            default=t.chave == "inicio",
        )
        for t in telas
    }
    if principal.administrador_acessos:
        P["controle_acesso"] = st.Page(
            nav.CONTROLE_ACESSO.arquivo,
            title=nav.CONTROLE_ACESSO.titulo,
            icon=nav.CONTROLE_ACESSO.icone,
            url_path=nav.CONTROLE_ACESSO.url,
        )
    st.session_state["_paginas"] = P

    atual = st.navigation(list(P.values()), position="hidden")
    chave_atual = next((k for k, p in P.items() if p.url_path == atual.url_path), "inicio")
    barra_lateral(nav.modulo_da_tela(chave_atual), chave_atual, principal)

    try:
        atual.run()
    except Exception as exc:  # st.stop()/st.rerun() herdam de BaseException e não são capturados aqui
        ref = nova_referencia()
        get_logger("app").exception("[%s] Erro ao abrir a tela %s", ref, chave_atual)
        st.error(
            f"Esta tela encontrou um erro e não pôde ser exibida (referência {ref}). "
            "As demais telas continuam disponíveis pela barra lateral. Detalhes em data/logs/sim.log.",
            icon=":material/error:",
        )
        with st.expander("Detalhes técnicos"):
            st.exception(exc)
        st.page_link(P["inicio"], label="Voltar ao início", icon=":material/home:")


principal = usuario_autenticado()
if principal is None:
    st.stop()

with usando_principal(principal):
    _executar(principal)
