"""SIM ASAP — Engenharia · Cadastro de centro de custo (Form2: só inclusão, RN-12)."""
from datetime import date

import streamlit as st

from sim.medicao import AJUDA_DIA, DIAS_MES, EXEMPLOS_PERIODO, descrever_periodo
from sim.services import asap
from sim.ui import common as ui
from sim.ui.encerramento import tabela_centros

NS = "asap_cc"
ROTULOS = {
    "titulo": "Centro de Custo", "cliente": "Cliente", "inicio_medicao": "Início de Medição",
    "fim_medicao": "Fim de Medição", "email": "E-mail", "periodo": "Período: Mensal ou Quinzenal",
}

ui.cabecalho("ASAP", "ENG", "Cadastro Centro de Custo",
             "Inclusão de centros de custo da ASAP. Como no app original, esta tela não edita nem exclui.")

ui.resumo_erros(NS, ROTULOS)
with ui.formulario():
    ui.secao("Centro de custo")
    a, b, c = st.columns(3)
    with a:
        st.text_input("Coligada", value="ASAP", disabled=True, key=f"{NS}-coligada-fixa",
                      help="Definida pelo caminho: este cadastro fica dentro do módulo ASAP.")
    with b:
        titulo = ui.campo_texto(NS, "titulo", "Centro de Custo", obrigatorio=True)
    with c:
        cliente = ui.campo_texto(NS, "cliente", "Cliente", obrigatorio=True)
    ui.secao("Medição")
    a, b, c = st.columns(3)
    with a:
        inicio = ui.campo_escolha(NS, "inicio_medicao", "Início de Medição (dia)", DIAS_MES, obrigatorio=True,
                                  ajuda=AJUDA_DIA)
    with b:
        fim = ui.campo_escolha(NS, "fim_medicao", "Fim de Medição (dia)", DIAS_MES, obrigatorio=True,
                               ajuda=AJUDA_DIA)
    with c:
        periodo = ui.campo_texto(NS, "periodo", "Período: Mensal ou Quinzenal",
                                 ajuda="Texto livre, como no original (P-09).")
    st.caption(EXEMPLOS_PERIODO)
    ui.secao("Contato")
    email = ui.campo_texto(NS, "email", "E-mail", obrigatorio=True, area=True, max_chars=None)
    salvar, limpar = ui.botoes_formulario(False, rotulo_cancelar="Cancelar")

if salvar:
    ui.executar(
        NS,
        lambda: asap.criar_centro_custo(
            {"titulo": titulo, "cliente": cliente, "inicio_medicao": inicio, "fim_medicao": fim,
             "email": email, "periodo": periodo}
        ),
        "Centro de custo cadastrado com sucesso.",
    )
if limpar:
    ui.reiniciar(NS)
    st.rerun()

# Consulta (melhoria documentada: o original não mostrava a lista nesta tela)
ccs = ui.carregar(asap.listar_centros_custo)
hoje = date.today()
st.subheader(f"Centros de custo cadastrados ({len(ccs)})", anchor=False)
tabela_centros(f"{NS}_ativo", "ASAP", ccs, [
    {
        "ID": c.id, "Centro de Custo": c.titulo, "Cliente": c.cliente,
        "Início de Medição": ui.formatar_numero(c.inicio_medicao),
        "Fim de Medição": ui.formatar_numero(c.fim_medicao),
        f"Período em {hoje:%m/%Y}": descrever_periodo(c.inicio_medicao, c.fim_medicao, hoje.year, hoje.month),
        "Período": c.periodo or "", "E-mail": c.email,
    }
    for c in ccs
])
