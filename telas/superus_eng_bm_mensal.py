"""SIM SUPERUS · BM Mensal (Gallery3_1 + Form1 do original)."""
import math
from decimal import Decimal

import pandas as pd
import streamlit as st

from sim.errors import NotFoundError
from sim.options import opcoes
from sim.services import previsto, superus
from sim.services.encerramento import MENSAGEM_CC_INATIVO
from sim.ui import common as ui
from sim.ui.superus import centro_custo_confirmado

NS = "sup_bm"
P = st.session_state["_paginas"]
ROTULOS = {
    "titulo": "Nome do Arquivo", "mes_referencia": "Mês de Referência", "tipo": "Tipo", "ano": "Ano",
    "valor_bm": "Valor BM/PO", "glosa": "Glosa", "postergado": "Postergado", "valor_aprovado": "Valor Aprovado",
    "status": "Status", "cidade": "Cidade do Serviço", "numero_contrato": "Nº do Contrato", "po": "PO",
    "anexos": "Anexos", "centro_custo_id": "Centro de Custo", "justificativa_variacao": "Justificativa da variação",
    "itens": "BMs do mês",
}
COL_DESC, COL_VALOR, COL_APROV = "BM (identificação)", "Valor do BM (R$)", "Valor aprovado (R$)"

ui.cabecalho("SUPERUS", "ENG", "BM Mensal", "Boletins de medição mensais do centro de custo escolhido.")
cc = centro_custo_confirmado(P.get("sup_cc"))

ui.secao("Filtros e atalhos")
c1, c2, c3 = st.columns([1.2, 1, 1], vertical_alignment="bottom")
mes_filtro = c1.selectbox("Filtro de Mês", list(opcoes("superus.mes_referencia").valores), index=None,
                          placeholder="Todos os meses", key=f"sup_bm_mes_{cc.id}")
if "sup_enc" in P:
    c2.page_link(P["sup_enc"], label="Fim Mês (Encerramento)", icon=":material/event_available:")
c3.page_link(P["sup_help"], label="Central de Ajuda", icon=":material/help:")

bms = ui.carregar(superus.listar_bms_mensais, centro_custo_id=cc.id, mes=mes_filtro)
st.subheader(f"BMs do centro de custo ({len(bms)})", anchor=False)
st.caption("Clique em uma linha para editar ou excluir.")
sel_id = ui.tabela(NS, [
    {
        "ID": b.id,
        "Nome do Arquivo": b.titulo,
        "Centro de Custo": cc.titulo,
        "Mês": b.mes_referencia,
        "Ano": b.ano,
        "Tipo": b.tipo,
        "Valor BM/PO": ui.moeda(b.valor_bm),
        "Glosa": ui.moeda(b.glosa or 0),
        "Postergado": ui.moeda(b.postergado or 0),
        "Valor Aprovado": ui.moeda(b.valor_aprovado or 0),
        "Valor Faturado (Emitido)": ui.moeda(b.valor_emitido or 0),
        "Status": b.status,
        "Anexos": ui.qtd_anexos(b.anexos),
    }
    for b in bms
], ctx=(cc.id, mes_filtro))

bm = None
if sel_id is not None:
    try:
        bm = superus.obter_bm_mensal(sel_id)
    except NotFoundError as exc:
        st.warning(exc.message)
        ui.reiniciar(NS)

st.divider()
editando = bm is not None
ctx = bm.id if editando else f"novo{cc.id}"
lida = ui.versao_lida(NS, bm, ctx)  # edição simultânea: versão aberta neste formulário
st.subheader(f"Editar BM #{bm.id}" if editando else "Novo BM", anchor=False)
if not editando and not cc.ativo:
    st.warning(MENSAGEM_CC_INATIVO + " Para reabri-lo, fale com o Controle.", icon=":material/block:")
    st.stop()
if editando:
    ui.anexos_download(NS, bm.anexos, ctx=ctx)

ui.resumo_erros(NS, ROTULOS)
v = (lambda campo: getattr(bm, campo)) if editando else (lambda campo: None)

# O mês fica fora do formulário para o valor previsto aparecer assim que é escolhido. O ano não é digitado:
# vem da data do lançamento (mês posterior ao atual é do ano anterior, ex.: dezembro lançado em janeiro).
ui.secao("Mês do BM")
st.caption("Cada mês tem uma única resposta por centro de custo: anexe todos os BMs do mês e informe o valor somado.")
a, b, c = st.columns([1, 1, 2], vertical_alignment="bottom")
with a:
    mes = ui.campo_escolha(NS, "mes_referencia", "Mês de Referência", superus.meses_para(bm),
                           v("mes_referencia"), obrigatorio=True, ctx=ctx,
                           ajuda="Só aparecem meses já iniciados: cada mês fica disponível a partir do dia 1º.")
ano = superus.ano_de_referencia(mes, bm)
with b:
    st.text_input("Ano", value=ano or "", disabled=True, help="Definido pelo SIM a partir da data do lançamento.")
ocupado = ui.carregar(superus.bm_do_mes, cc.id, mes, bm) if mes else None
if ocupado and (not editando or (mes, ano) != (bm.mes_referencia, bm.ano)):
    st.warning(superus.mensagem_mes_ocupado(ocupado, mes, ano), icon=":material/block:")
valor_previsto = ui.carregar(previsto.obter, cc.id, ano, mes)
with c:
    if not (mes and ano):
        st.caption("Escolha o mês para ver o valor previsto deste centro de custo.")
    elif valor_previsto is None:
        st.info(f"Não há valor previsto cadastrado para {mes}/{ano}.", icon=":material/info:")
    else:
        st.info(f"Valor previsto para {mes}/{ano}: **R$ {ui.moeda(valor_previsto)}**. Se a soma dos BMs ficar mais "
                "de 5% acima ou abaixo dele, será preciso justificar a variação.", icon=":material/insights:")

with ui.formulario():
    ui.secao("Identificação")
    a, b = st.columns(2)
    with a:
        st.text_input("Centro de Custo", value=cc.titulo, disabled=True, key=ui.chave(NS, "cc_view", ctx),
                      help="Vinculado ao centro de custo confirmado; não muda na edição.")
    with b:
        titulo = ui.campo_texto(NS, "titulo", "Nome do Arquivo", v("titulo"), obrigatorio=True, ctx=ctx)
    c, d = st.columns(2)
    with c:
        tipo = ui.campo_escolha(NS, "tipo", "Tipo", opcoes("superus.tipo"), v("tipo"), obrigatorio=True, ctx=ctx,
                                ajuda="Descrição do valor lançado (veja a Central de Ajuda).")
    with d:
        status = ui.campo_escolha(NS, "status", "Status", superus.status_permitidos_engenharia(v("status")),
                                  v("status"), obrigatorio=True, ctx=ctx)

    ui.secao("BMs do mês")
    st.caption("Lance uma linha por BM (todos os BMs do mês ficam nesta resposta). Use + no fim da tabela para "
               "incluir outro BM. O Valor BM/PO e o Valor Aprovado são as somas e não são digitados.")
    if editando and bm.itens:
        iniciais = [{COL_DESC: i.descricao, COL_VALOR: float(i.valor_bm),
                     COL_APROV: None if i.valor_aprovado is None else float(i.valor_aprovado)} for i in bm.itens]
    elif editando:  # BM do SIM antigo: o valor lançado vira a primeira linha
        iniciais = [{COL_DESC: bm.titulo, COL_VALOR: float(bm.valor_bm),
                     COL_APROV: None if bm.valor_aprovado is None else float(bm.valor_aprovado)}]
    else:
        iniciais = [{COL_DESC: None, COL_VALOR: None, COL_APROV: None}]
    tabela_itens = st.data_editor(
        pd.DataFrame(iniciais, columns=[COL_DESC, COL_VALOR, COL_APROV]),
        key=ui.chave(NS, "itens", ctx), num_rows="dynamic", hide_index=True, width="stretch",
        column_config={
            COL_DESC: st.column_config.TextColumn(help="Número ou nome do BM, ex.: BM 33 OPEX", max_chars=255),
            COL_VALOR: st.column_config.NumberColumn(min_value=0, step=0.01, format="localized"),
            COL_APROV: st.column_config.NumberColumn(min_value=0, step=0.01, format="localized"),
        },
    )
    ui.erro_campo(NS, "itens")

    def _valor(x):
        return None if x is None or (isinstance(x, float) and math.isnan(x)) else Decimal(str(round(float(x), 2)))

    itens = [{"descricao": r[COL_DESC], "valor_bm": _valor(r[COL_VALOR]), "valor_aprovado": _valor(r[COL_APROV])}
             for r in tabela_itens.to_dict("records")]
    total_bm = sum((i["valor_bm"] for i in itens if i["valor_bm"] is not None), Decimal(0))
    aprovados = [i["valor_aprovado"] for i in itens if i["valor_aprovado"] is not None]
    total_aprovado = sum(aprovados, Decimal(0)) if aprovados else None

    a, b, c, d = st.columns(4)
    a.text_input("Valor BM/PO (soma dos BMs)", value=f"R$ {ui.moeda(total_bm)}", disabled=True)
    b.text_input("Valor Aprovado (soma dos BMs)",
                 value=f"R$ {ui.moeda(total_aprovado)}" if total_aprovado is not None else "", disabled=True)
    with c:
        glosa = ui.campo_moeda(NS, "glosa", "Glosa", v("glosa"), ctx=ctx)
    with d:
        postergado = ui.campo_moeda(NS, "postergado", "Postergado", v("postergado"), ctx=ctx)

    # Variação sobre o previsto, acompanhando a soma enquanto o gestor digita.
    justificativa = None
    fora = valor_previsto is not None and total_bm > 0 and previsto.fora_da_tolerancia(total_bm, valor_previsto)
    if fora or (editando and bm.justificativa_variacao):
        ui.secao("Variação sobre o previsto")
        if fora:
            st.warning(previsto.pergunta(total_bm, valor_previsto), icon=":material/insights:")
        justificativa = ui.campo_texto(NS, "justificativa_variacao", "Justificativa da variação",
                                       v("justificativa_variacao"), area=True, obrigatorio=fora, ctx=ctx)
    elif valor_previsto is not None and total_bm > 0:
        st.caption(f"Soma dentro da variação de 5% do previsto (R$ {ui.moeda(valor_previsto)}).")

    ui.secao("Contrato e serviço")
    a, b, c = st.columns(3)
    with a:
        cidade = ui.campo_texto(NS, "cidade", "Cidade do Serviço", v("cidade"), obrigatorio=True, ctx=ctx)
    with b:
        contrato = ui.campo_texto(NS, "numero_contrato", "Nº do Contrato", v("numero_contrato"), obrigatorio=True,
                                  ctx=ctx)
    with c:
        po = ui.campo_texto(NS, "po", "PO", v("po"), ctx=ctx)

    ui.secao("Anexos")
    remover = ui.anexos_remover(NS, bm.anexos, ctx=ctx) if editando else []
    novos = ui.campo_anexos(NS, "Adicionar anexos" if editando else "Anexos", obrigatorio=not editando, ctx=ctx)
    salvar, cancelar = ui.botoes_formulario(editando)

dados = {
    "titulo": titulo, "mes_referencia": mes, "tipo": tipo, "ano": ano, "itens": itens, "glosa": glosa,
    "postergado": postergado, "status": status, "cidade": cidade,
    "numero_contrato": contrato, "po": po, "justificativa_variacao": justificativa,
}
if salvar:
    if editando:
        ui.executar(NS, lambda: superus.atualizar_bm_mensal(bm.id, dados, novos, remover, versao=lida), f"BM #{bm.id} atualizado.")
    else:
        ui.executar(NS, lambda: superus.criar_bm_mensal(cc.id, dados, novos), "BM cadastrado com sucesso.")
if cancelar:
    ui.reiniciar(NS)
    st.rerun()

if editando and ui.botao_excluir(NS, "Excluir este BM", bm.id):
    ui.confirmar_exclusao(
        NS, f"BM **#{bm.id} — {bm.titulo}** ({cc.titulo}, {bm.mes_referencia}/{bm.ano})",
        lambda: superus.excluir_bm_mensal(bm.id, versao=lida), f"BM #{bm.id} excluído.",
    )
