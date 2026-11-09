"""Mapa de navegação do SIM (dados puros, sem Streamlit — testável).

Fluxo:
  Início (Bem-vindo ao SIM)
   ├─ ASAP ............... módulo ASAP (BM Mensal, Cadastro; código interno "ENG")
   ├─ SUPERUS ............ módulo SUPERUS — operacional (BM Mensal, BM Semanal, Cadastro, Encerramento, Ajuda)
   └─ Administrativo ..... seleção de empresa
        ├─ ASAP ADM ....... módulo ASAP — Administrativo (Faturamento)
        └─ SUPERUS ADM .... módulo SUPERUS — Administrativo (Faturamento, Planejamento, Valor Previsto,
                            Atualizar dados)

Cada tela pertence a exatamente um módulo; a barra lateral mostra só as telas do módulo atual.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tela:
    chave: str
    arquivo: str  # caminho relativo à raiz do projeto
    titulo: str
    icone: str  # ícone Material (":material/nome:")
    url: str
    resumo: str = ""  # uma linha, exibida na tela inicial do módulo


@dataclass(frozen=True)
class Modulo:
    chave: str
    empresa: str  # "ASAP" | "SUPERUS"
    tipo: str  # "ENG" | "ADM"
    titulo: str
    descricao: str
    entrada: Tela  # tela inicial do módulo
    telas: tuple[Tela, ...] = field(default_factory=tuple)


INICIO = Tela("inicio", "telas/inicio.py", "Início", ":material/home:", "")
SELECAO_ADM = Tela("adm_selecao", "telas/adm_selecao.py", "Administrativo", ":material/apartment:", "administrativo")
CONTROLE_ACESSO = Tela(
    "controle_acesso",
    "telas/controle_acesso.py",
    "Controle de acesso",
    ":material/admin_panel_settings:",
    "controle-acesso",
)

MODULOS: dict[str, Modulo] = {
    "asap_eng": Modulo(
        "asap_eng", "ASAP", "ENG", "ASAP",
        "Lançamento e acompanhamento dos BMs mensais e cadastro de centros de custo.",
        Tela("asap_eng", "telas/modulo_asap_eng.py", "Visão geral", ":material/dashboard:", "asap"),
        (
            Tela("asap_bm", "telas/asap_eng_bm_mensal.py", "BM Mensal", ":material/description:", "asap-bm-mensal", "Lançar, consultar, editar e excluir BMs mensais com anexos."),
            Tela("asap_cc", "telas/asap_eng_cadastro.py", "Cadastro Centro de Custo", ":material/sell:",
                 "asap-cadastro", "Incluir novos centros de custo da ASAP."),
            Tela("asap_enc", "telas/asap_eng_encerramento.py", "Encerramento", ":material/event_available:",
                 "asap-encerramento", "Solicitar ou decidir o encerramento de um centro de custo."),
        ),
    ),
    "sup_eng": Modulo(
        "sup_eng", "SUPERUS", "ENG", "SUPERUS",
        "BMs mensais e semanais por centro de custo, cadastro, encerramento e central de ajuda.",
        Tela("sup_eng", "telas/modulo_superus_eng.py", "Visão geral", ":material/dashboard:", "superus"),
        (
            Tela("sup_bm", "telas/superus_eng_bm_mensal.py", "BM Mensal", ":material/description:",
                 "superus-bm-mensal", "BMs mensais do centro de custo escolhido."),
            Tela("sup_sem", "telas/superus_eng_bm_semanal.py", "BM Semanal", ":material/date_range:",
                 "superus-bm-semanal", "BMs semanais (valor acumulado) do centro de custo."),
            Tela("sup_cc", "telas/superus_eng_cadastro.py", "Cadastro Centro de Custo", ":material/sell:",
                 "superus-cadastro", "Incluir novos centros de custo da Superus."),
            Tela("sup_enc", "telas/superus_eng_encerramento.py", "Encerramento", ":material/event_available:",
                 "superus-encerramento", "Solicitar ou decidir o encerramento de um centro de custo."),
            Tela("sup_help", "telas/superus_eng_help.py", "Central de Ajuda", ":material/help:", "superus-help", "Glossário dos campos do BM."),
        ),
    ),
    "asap_adm": Modulo(
        "asap_adm", "ASAP", "ADM", "ASAP ADM",
        "Conferência dos BMs e registro do faturamento: valor emitido, status e anexos.",
        Tela("asap_adm", "telas/modulo_asap_adm.py", "Visão geral", ":material/dashboard:", "asap-adm"),
        (
            Tela("asap_fat", "telas/asap_adm_faturamento.py", "Faturamento", ":material/request_quote:",
                 "asap-faturamento", "Valor emitido, status e anexos dos BMs."),
        ),
    ),
    "sup_adm": Modulo(
        "sup_adm", "SUPERUS", "ADM", "SUPERUS ADM",
        "Faturamento, planejamento (consulta mensal e semanal), valor previsto e atualização de dados dos centros "
        "de custo.",
        Tela("sup_adm", "telas/modulo_superus_adm.py", "Visão geral", ":material/dashboard:", "superus-adm"),
        (
            Tela("sup_fat", "telas/superus_adm_faturamento.py", "Faturamento", ":material/request_quote:",
                 "superus-faturamento", "Status, valores liberado e emitido, FRS, PO e anexos."),
            Tela("sup_plan", "telas/superus_adm_planejamento.py", "Planejamento", ":material/calendar_month:",
                 "superus-planejamento", "Consulta dos BMs mensais e semanais."),
            Tela("sup_prev", "telas/superus_adm_valor_previsto.py", "Valor Previsto", ":material/insights:",
                 "superus-valor-previsto", "Previsto do mês por centro de custo (preenchido pelo Controle)."),
            Tela("sup_atu", "telas/superus_adm_atualizar_dados.py", "Atualizar dados", ":material/edit_note:",
                 "superus-atualizar-dados", "Quantidade de BMs, cidade e nº do contrato dos CCs."),
        ),
    ),
}

# Cartões da tela inicial: exatamente três áreas.
AREAS_INICIO = (
    ("asap_eng", "ASAP", "ASAP"),
    ("sup_eng", "SUPERUS", "SUPERUS"),
    ("adm", "OES", "Administrativo"),
)
# Opções da seleção administrativa.
OPCOES_ADM = ("asap_adm", "sup_adm")

NOME_TIPO = {"ENG": "Engenharia", "ADM": "Administrativo"}
# SUPERUS reúne as coligadas Superus Engenharia, ACPL e Superus Holding (ver superus.COLIGADAS).
NOME_EMPRESA = {"ASAP": "ASAP", "SUPERUS": "SUPERUS"}


def nome_tipo(empresa: str, tipo: str) -> str:
    """Rótulo visível da área do módulo. "ENG" é só o código interno do módulo operacional e não
    aparece: as áreas operacionais se chamam apenas ASAP e SUPERUS (decisão de 2026-10-27)."""
    if tipo == "ENG":
        return ""
    return NOME_TIPO[tipo]


def todas_as_telas() -> list[Tela]:
    telas = [INICIO, SELECAO_ADM, CONTROLE_ACESSO]
    for m in MODULOS.values():
        telas.append(m.entrada)
        telas.extend(m.telas)
    return telas


def modulo_da_tela(chave_tela: str) -> Modulo | None:
    for m in MODULOS.values():
        if chave_tela == m.entrada.chave or any(t.chave == chave_tela for t in m.telas):
            return m
    return None


def modulo_por_empresa(empresa: str, tipo: str) -> Modulo:
    for m in MODULOS.values():
        if m.empresa == empresa and m.tipo == tipo:
            return m
    raise KeyError((empresa, tipo))


def migalhas(empresa: str, tipo: str, titulo_tela: str | None) -> list[str]:
    """Indicador de navegação, ex.: O&S Gestão › ASAP › BM Mensal
    ou O&S Gestão › Administrativo › ASAP ADM › Faturamento."""
    m = modulo_por_empresa(empresa, tipo)
    itens = ["O&S Gestão"]
    if tipo == "ADM":
        itens.append("Administrativo")
    itens.append(m.titulo)
    if titulo_tela:
        itens.append(titulo_tela)
    return itens
