"""Identidade visual do SIM: paleta, logotipos e CSS centralizados.

Cores extraídas dos logotipos oficiais (assets/logos), sem inventar cores novas:
- O&S Gestão (identidade principal): petróleo #00495C e lima #C5EA2A (detalhe do logotipo).
- ASAP: azul #1641FF e azul escuro #0027AF.
- SUPERUS: verde escuro #25382D e verde-lima #97C03B.
Os neutros (fundos, bordas, textos) são derivados do petróleo da O&S.
O lima da O&S e o verde-lima da Superus têm pouco contraste sobre branco: são usados só
em faixas e detalhes decorativos, nunca em textos.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sim.config import BASE_DIR

LOGOS_DIR = BASE_DIR / "assets" / "logos"

PALETA = {
    "oes": "#00495C",
    "oes_escuro": "#003746",
    "oes_claro": "#E6EFF1",
    "oes_lima": "#C5EA2A",
    "texto": "#13262D",
    "texto_suave": "#56676D",
    "borda": "#D9E2E5",
    "fundo": "#F4F7F8",
    "superficie": "#FFFFFF",
    "perigo": "#B42318",
    "perigo_claro": "#FDECEA",
}


@dataclass(frozen=True)
class Identidade:
    codigo: str
    nome: str
    logo: str  # arquivo em assets/logos
    cor: str  # cor principal (texto e destaques)
    cor_escura: str
    cor_detalhe: str  # faixas decorativas
    cor_clara: str  # fundos suaves


IDENTIDADES = {
    "OES": Identidade("OES", "O&S Gestão", "oes-gestao.jpg", PALETA["oes"], PALETA["oes_escuro"],
                      PALETA["oes_lima"], PALETA["oes_claro"]),
    "ASAP": Identidade("ASAP", "ASAP", "asap.png", "#1641FF", "#0027AF", "#1641FF", "#E8EDFF"),
    "SUPERUS": Identidade("SUPERUS", "SUPERUS", "superus-engenharia.png", "#25382D", "#25382D",
                          "#97C03B", "#EEF5E4"),
}

NOME_SISTEMA = "Sistema Integrado de Medições"


def caminho_logo(codigo: str) -> Path:
    return LOGOS_DIR / IDENTIDADES[codigo].logo


@lru_cache(maxsize=8)
def logo_data_uri(codigo: str) -> str:
    """Logotipo original embutido em base64 (arquivos pequenos), para uso em HTML."""
    caminho = caminho_logo(codigo)
    mime = "image/jpeg" if caminho.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    return f"data:{mime};base64,{base64.b64encode(caminho.read_bytes()).decode()}"


def img_logo(codigo: str, classe: str, alt: str | None = None) -> str:
    alt = alt or f"Logotipo {IDENTIDADES[codigo].nome}"
    return f'<img src="{logo_data_uri(codigo)}" class="{classe}" alt="{alt}">'


P = PALETA

CSS = f"""
<style>
/* ---------- base ---------- */
/* A barra superior do Streamlit (stHeader) é fixa, branca e tem 3.75rem de altura:
   o conteúdo precisa começar abaixo dela, senão o cabeçalho do SIM fica encoberto. */
.block-container {{padding-top: calc(3.75rem + 1.25rem); padding-bottom: 3rem; max-width: 1280px;}}
h1, h2, h3 {{letter-spacing: -0.01em; color: {P['texto']};}}
h1 {{font-size: 1.75rem !important; font-weight: 700 !important;}}
h3 {{font-size: 1.15rem !important;}}

/* ---------- cabeçalho ---------- */
.sim-topo {{display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  background: {P['superficie']}; border: 1px solid {P['borda']}; border-radius: 12px;
  padding: .6rem .9rem; margin-bottom: 1rem; position: relative; overflow: hidden;}}
.sim-topo::after {{content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px;
  background: linear-gradient(90deg, {P['oes']} 0%, {P['oes']} 70%, var(--sim-acento, {P['oes_lima']}) 100%);}}
.sim-topo__marca {{display: flex; align-items: center; gap: .8rem; min-width: 0;}}
.sim-topo__oes {{width: 44px; height: 44px; border-radius: 10px; flex: none; object-fit: contain;}}
.sim-topo__sistema {{font-weight: 700; color: {P['oes']}; font-size: .95rem; line-height: 1.2;}}
.sim-migalhas {{font-size: .8rem; color: {P['texto_suave']}; margin-top: .15rem; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;}}
.sim-migalhas b {{color: {P['texto']}; font-weight: 600;}}
.sim-migalhas span {{margin: 0 .3rem; opacity: .6;}}
.sim-topo__coligada {{height: 40px; width: auto; max-width: 140px; object-fit: contain; flex: none;}}

/* ---------- título da tela ---------- */
.sim-chips {{display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .1rem;}}
.sim-chip {{font-size: .72rem; font-weight: 600; letter-spacing: .03em; text-transform: uppercase;
  padding: .15rem .55rem; border-radius: 999px; background: var(--sim-cor-clara); color: var(--sim-cor);}}
.sim-sub {{color: {P['texto_suave']}; font-size: .92rem; margin: -.4rem 0 .9rem 0;}}

/* ---------- seções de formulário ---------- */
.sim-secao {{font-size: .78rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase;
  color: {P['oes']}; border-bottom: 1px solid {P['borda']}; padding-bottom: .3rem; margin: .4rem 0 .2rem 0;}}

/* ---------- cartões de área ---------- */
.sim-cartao {{display: flex; flex-direction: column; align-items: flex-start; gap: .55rem; min-height: 100%;
  padding-bottom: .5rem;}}
.sim-atalho__texto {{color: {P['texto_suave']}; font-size: .84rem; margin: -.35rem 0 0 .2rem; line-height: 1.4;}}
.sim-cartao__logo {{height: 84px; width: auto; max-width: 100%; object-fit: contain;}}
.sim-cartao__logo--oes {{height: 84px; width: 84px; border-radius: 16px;}}
.sim-cartao__titulo {{font-size: 1.2rem; font-weight: 700; color: {P['texto']}; margin-top: .3rem;}}
.sim-cartao__texto {{color: {P['texto_suave']}; font-size: .92rem; line-height: 1.45;}}
.sim-cartao__faixa {{height: 4px; width: 56px; border-radius: 4px; background: var(--sim-cor-detalhe);}}

/* ---------- boas-vindas ---------- */
.sim-boasvindas {{display: flex; align-items: center; gap: 1.1rem; margin: .5rem 0 1.4rem 0;}}
.sim-boasvindas img {{width: 72px; height: 72px; border-radius: 16px;}}
.sim-boasvindas h1 {{margin: 0; padding: 0;}}
.sim-boasvindas p {{margin: .2rem 0 0 0; color: {P['texto_suave']};}}

/* ---------- estados vazios ---------- */
.sim-vazio {{border: 1px dashed {P['borda']}; border-radius: 12px; padding: 1.4rem; text-align: center;
  color: {P['texto_suave']}; background: {P['superficie']};}}
.sim-vazio b {{display: block; color: {P['texto']}; margin-bottom: .2rem;}}

/* ---------- barra lateral ---------- */
.sim-lateral-area {{display: flex; align-items: center; gap: .6rem; padding: .6rem 0 .6rem 0;
  margin-top: .4rem; border-top: 1px solid {P['borda']};}}
.sim-lateral-area img {{height: 30px; width: auto; max-width: 90px; object-fit: contain;}}
.sim-lateral-area div {{font-size: .78rem; line-height: 1.25; color: {P['texto_suave']};}}
.sim-lateral-area b {{display: block; color: {P['texto']}; font-size: .88rem;}}
.sim-rodape {{font-size: .72rem; color: {P['texto_suave']}; line-height: 1.4;}}

/* ---------- botões ---------- */
.stButton button, .stFormSubmitButton button, .stDownloadButton button {{font-weight: 600;}}
/* Excluir: vermelho, distinto de Salvar (primário) e Cancelar (secundário) */
[class*="st-key-excluir"] button {{background: {P['superficie']}; color: {P['perigo']};
  border: 1px solid {P['perigo']};}}
[class*="st-key-excluir"] button:hover {{background: {P['perigo_claro']}; color: {P['perigo']};
  border-color: {P['perigo']};}}
[class*="st-key-confirmar-exclusao"] button {{background: {P['perigo']}; color: #fff; border: 1px solid {P['perigo']};}}
[class*="st-key-confirmar-exclusao"] button:hover {{background: #8f1c13; color: #fff;}}

/* ---------- celular ---------- */
@media (max-width: 640px) {{
  .block-container {{padding-top: calc(3.75rem + .75rem);}}  /* abaixo da barra superior do Streamlit */
  .sim-topo {{padding: .5rem .6rem;}}
  .sim-topo__coligada {{height: 30px; max-width: 90px;}}
  .sim-migalhas {{white-space: normal;}}
  .sim-boasvindas img {{width: 52px; height: 52px;}}
  h1 {{font-size: 1.4rem !important;}}
}}
</style>
"""
