"""SIM SUPERUS · BM Semanal (Gallery3_2 + Form1_1). Não tem Status no original."""
import streamlit as st

from sim.errors import NotFoundError
from sim.options import opcoes
from sim.services import superus
from sim.services.encerramento import MENSAGEM_CC_INATIVO
from sim.ui import common as ui
from sim.ui.superus import centro_custo_confirmado

NS = "sup_sem"
P = st.session_state["_paginas"]
ROTULOS = {"titulo": "Nome do Arquivo", "mes_referencia": "Mês de Referência", "semana": "Semana do BM",
           "valor_bm": "Valor Acumulado do BM", "anexos": "Anexos"}

ui.cabecalho("SUPERUS", "ENG", "BM Semanal", "Boletins de medição semanais do centro de custo escolhido.")
cc = centro_custo_confirmado(P.get("sup_cc"))

ui.secao("Filtros e atalhos")
f1, f2, f3 = st.columns([1, 1, 1], vertical_alignment="bottom")
mes_f = f1.selectbox("Filtro de Mês", list(opcoes("superus.mes_referencia").valores), index=None,
                     placeholder="Todos", key=f"sup_sem_mes_{cc.id}")
sem_f = f2.selectbox("Filtro de Semana", list(opcoes("superus.semana").valores), index=None,
                     placeholder="Todas", key=f"sup_sem_sem_{cc.id}")
f3.page_link(P["sup_help"], label="Central de Ajuda", icon=":material/help:")

bms = ui.carregar(superus.listar_bms_semanais, centro_custo_id=cc.id, mes=mes_f, semana=sem_f)
st.subheader(f"BMs semanais ({len(bms)})", anchor=False)
st.caption("Clique em uma linha para editar ou excluir.")
sel_id = ui.tabela(NS, [
    {
        "ID": b.id, "Centro de Custo": cc.titulo, "Nome do Arquivo": b.titulo, "Mês": b.mes_referencia,
        "Semana": b.semana, "Valor Acumulado do BM": ui.moeda(b.valor_bm), "Anexos": ui.qtd_anexos(b.anexos),
    }
    for b in bms
], ctx=(cc.id, mes_f, sem_f))

bm = None
if sel_id is not None:
    try:
        bm = superus.obter_bm_semanal(sel_id)
    except NotFoundError as exc:
        st.warning(exc.message)
        ui.reiniciar(NS)

st.divider()
editando = bm is not None
ctx = bm.id if editando else f"novo{cc.id}"
lida = ui.versao_lida(NS, bm, ctx)  # edição simultânea: versão aberta neste formulário
st.subheader(f"Editar BM semanal #{bm.id}" if editando else "Novo BM semanal", anchor=False)
if not editando and not cc.ativo:
    st.warning(MENSAGEM_CC_INATIVO + " Para reabri-lo, fale com o Controle.", icon=":material/block:")
    st.stop()
if editando:
    ui.anexos_download(NS, bm.anexos, ctx=ctx)

ui.resumo_erros(NS, ROTULOS)
with ui.formulario():
    ui.secao("Identificação")
    a, b = st.columns(2)
    with a:
        st.text_input("Centro de Custo", value=cc.titulo, disabled=True, key=ui.chave(NS, "cc_view", ctx))
    with b:
        titulo = ui.campo_texto(NS, "titulo", "Nome do Arquivo", bm.titulo if editando else "", obrigatorio=True,
                                ctx=ctx)
    ui.secao("Período e valor")
    a, b, c = st.columns(3)
    with a:
        mes = ui.campo_escolha(NS, "mes_referencia", "Mês de Referência", opcoes("superus.mes_referencia"),
                               bm.mes_referencia if editando else None, obrigatorio=True, ctx=ctx)
    with b:
        semana = ui.campo_escolha(NS, "semana", "Semana do BM", opcoes("superus.semana"),
                                  bm.semana if editando else None, obrigatorio=True, ctx=ctx)
    with c:
        valor = ui.campo_moeda(NS, "valor_bm", "Valor Acumulado do BM", bm.valor_bm if editando else None,
                               obrigatorio=True, ctx=ctx,
                               ajuda="Valor acumulado até a semana, conforme o rótulo do original.")
    ui.secao("Anexos")
    remover = ui.anexos_remover(NS, bm.anexos, ctx=ctx) if editando else []
    novos = ui.campo_anexos(NS, "Adicionar anexos" if editando else "Anexos", obrigatorio=not editando, ctx=ctx)
    salvar, cancelar = ui.botoes_formulario(editando)

dados = {"titulo": titulo, "mes_referencia": mes, "semana": semana, "valor_bm": valor}
if salvar:
    if editando:
        ui.executar(NS, lambda: superus.atualizar_bm_semanal(bm.id, dados, novos, remover, versao=lida),
                    f"BM semanal #{bm.id} atualizado.")
    else:
        ui.executar(NS, lambda: superus.criar_bm_semanal(cc.id, dados, novos), "BM semanal cadastrado com sucesso.")
if cancelar:
    ui.reiniciar(NS)
    st.rerun()

if editando and ui.botao_excluir(NS, "Excluir este BM semanal", bm.id):
    ui.confirmar_exclusao(
        NS, f"BM semanal **#{bm.id} — {bm.titulo}** ({bm.mes_referencia}, {bm.semana})",
        lambda: superus.excluir_bm_semanal(bm.id, versao=lida), f"BM semanal #{bm.id} excluído.",
    )
