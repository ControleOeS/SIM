"""SIM SUPERUS · Cadastro de Centro de Custo (Form2 do original)."""
from datetime import date

import streamlit as st

from sim.medicao import AJUDA_DIA, DIAS_MES, EXEMPLOS_PERIODO, descrever_periodo
from sim.services import superus
from sim.ui import common as ui
from sim.ui.encerramento import tabela_centros

NS = "sup_cc"
ROTULOS = {"coligada": "Coligada", "titulo": "Centro de Custo", "gestor_obra": "Nome do Gestor",
           "obra_cliente": "Obra/Cliente", "inicio_medicao": "Início de Medição", "fim_medicao": "Fim de Medição"}

ui.cabecalho("SUPERUS", "ENG", "Cadastro de Centro de Custo")
st.info(
    "**Antes de cadastrar**, confira na lista abaixo se o centro de custo já existe. "
    f"O SIM também bloqueia duplicidade automaticamente. Critério: {superus.CRITERIO_DUPLICIDADE}"
)

ui.resumo_erros(NS, ROTULOS)
with ui.formulario():
    a, b = st.columns(2)
    with a:
        coligada = ui.campo_escolha(NS, "coligada", "Coligada", superus.COLIGADAS, obrigatorio=True,
                                    ajuda="O módulo SUPERUS reúne Superus Engenharia, ACPL e Superus Holding.")
    with b:
        titulo = ui.campo_texto(NS, "titulo", "Centro de Custo", obrigatorio=True, ajuda="Código do centro de custo.")
    a, b = st.columns(2)
    with a:
        gestor = ui.campo_texto(NS, "gestor_obra", "Nome do Gestor do Centro de custo", obrigatorio=True)
    with b:
        obra = ui.campo_texto(
            NS, "obra_cliente", "Nome completo do Cliente", obrigatorio=True,
            ajuda="Não preencher só: HYDRO. Coloque o nome inteiro, como: HYDRO PARAGOMINAS ANDAIME",
        )
    a, b = st.columns(2)
    with a:
        inicio = ui.campo_escolha(NS, "inicio_medicao", "Início de Medição (dia)", DIAS_MES, obrigatorio=True,
                                  ajuda=AJUDA_DIA)
    with b:
        fim = ui.campo_escolha(NS, "fim_medicao", "Fim de Medição (dia)", DIAS_MES, obrigatorio=True,
                               ajuda=AJUDA_DIA)
    st.caption(EXEMPLOS_PERIODO)
    salvar, cancelar = ui.botoes_formulario(False, rotulo_cancelar="Cancelar")

if salvar:
    ui.executar(
        NS,
        lambda: superus.criar_centro_custo({
            "coligada": coligada, "titulo": titulo, "gestor_obra": gestor, "obra_cliente": obra,
            "inicio_medicao": inicio, "fim_medicao": fim,
        }),
        "Cadastro realizado com sucesso!",
    )
if cancelar:
    ui.reiniciar(NS)
    st.rerun()

ccs = ui.carregar(superus.listar_centros_custo)
hoje = date.today()
st.subheader(f"Centros de custo cadastrados ({len(ccs)})", anchor=False)
tabela_centros(f"{NS}_ativo", "SUPERUS", ccs, [
    {"ID": c.id, "Centro de Custo": c.titulo, "Coligada": c.coligada, "Obra/Cliente": c.obra_cliente,
     "Gestor": c.gestor_obra, "Início de Medição": ui.formatar_numero(c.inicio_medicao),
     "Fim de Medição": ui.formatar_numero(c.fim_medicao),
     f"Período em {hoje:%m/%Y}": descrever_periodo(c.inicio_medicao, c.fim_medicao, hoje.year, hoje.month)}
    for c in ccs
])
