"""SIM SUPERUS — Administrativo · Faturamento (Gallery5 + Form2 + filtros do Form4).

Correções: só grava sobre um BM selecionado (nunca cria); sucesso só após o commit;
"Limpar filtros" reinicia todos os filtros (no original, só o de centro de custo).
"""
import streamlit as st

from sim.errors import NotFoundError
from sim.options import opcoes
from sim.services import previsto, superus
from sim.ui import common as ui

NS = "sup_fat"
NSF = "sup_fat_filtros"
ROTULOS = {"status": "Status", "valor_liberado": "Valor Liberado", "valor_emitido": "Valor Emitido",
           "mes_referencia": "Mês", "frs": "FRS", "po": "PO", "anexos": "Anexos"}

ui.cabecalho("SUPERUS", "ADM", "Faturamento", "Liberação e emissão dos BMs mensais da SUPERUS.")

op = ui.carregar(superus.opcoes_filtro_faturamento)
cc_por_id = {c.id: c for c in op["centros"]}

with st.container(border=True):
    ui.secao("Filtros")
    f1, f2, f3, f4, f5 = st.columns([1.3, 1.2, 1, 1, 0.7], vertical_alignment="bottom")
    cc_id = f1.selectbox("Centro de Custo", list(cc_por_id), index=None, placeholder="Todos",
                         format_func=lambda i: cc_por_id[i].titulo, key=ui.chave(NSF, "cc"))
    status_f = f2.selectbox("Status", op["status"], index=None, placeholder="Todos", key=ui.chave(NSF, "status"))
    mes_f = f3.selectbox("Mês", op["meses"], index=None, placeholder="Todos", key=ui.chave(NSF, "mes"))
    po_f = f4.text_input("PO (contém)", key=ui.chave(NSF, "po"), placeholder="Trecho do PO")
    if f5.button("Limpar filtros", width="stretch", icon=ui.ICONE["filtro_limpar"]):
        ui.reiniciar(NSF)
        ui.reiniciar(NS)
        st.rerun()

bms = ui.carregar(superus.listar_bms_mensais, centro_custo_id=cc_id, status=status_f, mes=mes_f, po=po_f)
st.subheader(f"BMs ({len(bms)})", anchor=False)
st.caption("Clique em uma linha para alterar os dados de faturamento.")
sel_id = ui.tabela(NS, [
    {
        "ID": b.id,
        "Centro de Custo": b.centro_custo.titulo,
        "Cliente": b.centro_custo.obra_cliente,
        "Mês": b.mes_referencia,
        "Ano": b.ano,
        "Cidade do Serviço": b.cidade,
        "Valor BM/PO": ui.moeda(b.valor_bm),
        "BM Aprovado": ui.moeda(b.valor_aprovado),
        "Valor Liberado": ui.moeda(b.valor_liberado),
        "Valor Emitido": ui.moeda(b.valor_emitido),
        "Glosa": ui.moeda(b.glosa),
        "FRS": ui.formatar_numero(b.frs),
        "PO": b.po or "",
        "Status": b.status,
        "Anexos": ui.qtd_anexos(b.anexos),
    }
    for b in bms
], ctx=(cc_id, status_f, mes_f, po_f))

st.divider()
if sel_id is None:
    ui.versao_lida(NS, None)
    st.info("Selecione um BM na tabela para alterar. Esta tela não cria BMs.", icon=":material/touch_app:")
    st.stop()
try:
    bm = superus.obter_bm_mensal(sel_id)
except NotFoundError as exc:
    st.warning(exc.message)
    ui.reiniciar(NS)
    st.stop()

st.subheader(f"Alterar BM #{bm.id} — {bm.titulo}", anchor=False)
lida = ui.versao_lida(NS, bm, bm.id)  # edição simultânea: versão aberta neste formulário
ui.secao("Valores da engenharia (somente consulta)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Valor BM/PO", ui.moeda(bm.valor_bm) or "—")
c2.metric("Valor Aprovado", ui.moeda(bm.valor_aprovado) or "—")
c3.metric("Glosa", ui.moeda(bm.glosa) or "—")
c4.metric("Postergado", ui.moeda(bm.postergado) or "—")
st.caption(f"Centro de custo {bm.centro_custo.titulo} · {bm.centro_custo.obra_cliente} · Cidade {bm.cidade} · "
           f"Contrato {bm.numero_contrato}. Valor Aprovado e Glosa são apenas para consulta nesta tela.")
if bm.itens:
    st.markdown(f"**BMs desta resposta ({len(bm.itens)})**")
    st.dataframe(
        [{"BM": i.descricao, "Valor do BM": ui.moeda(i.valor_bm), "Valor aprovado": ui.moeda(i.valor_aprovado)}
         for i in bm.itens],
        hide_index=True, width="stretch",
    )
if bm.valor_previsto is not None or bm.justificativa_variacao:
    texto = f"Valor previsto do mês: R$ {ui.moeda(bm.valor_previsto)}." if bm.valor_previsto is not None else ""
    if bm.justificativa_variacao:
        st.warning(f"{texto} O BM fugiu mais de 5% do previsto. Justificativa do gestor:\n\n"
                   f"{bm.justificativa_variacao}", icon=":material/insights:")
    elif previsto.fora_da_tolerancia(bm.valor_bm, bm.valor_previsto):
        st.caption(texto + " Fora da variação de 5%, sem justificativa (BM lançado no SIM antigo).")
    else:
        st.caption(texto + " Dentro da variação de 5%.")
ui.anexos_download(NS, bm.anexos, ctx=bm.id)

ui.resumo_erros(NS, ROTULOS)
with ui.formulario():
    ui.secao("Faturamento")
    a, b, c = st.columns(3)
    with a:
        status = ui.campo_escolha(NS, "status", "Status", opcoes("superus.status"), bm.status, obrigatorio=True,
                                  ctx=bm.id)
    with b:
        valor_liberado = ui.campo_moeda(NS, "valor_liberado", "Valor Liberado", bm.valor_liberado, ctx=bm.id)
    with c:
        valor_emitido = ui.campo_moeda(NS, "valor_emitido", "Valor Emitido", bm.valor_emitido, ctx=bm.id)
    ui.secao("Referências")
    a, b, c = st.columns(3)
    with a:
        mes = ui.campo_escolha(NS, "mes_referencia", "Mês", superus.meses_para(bm), bm.mes_referencia,
                               obrigatorio=True, ctx=bm.id)
    with b:
        frs = ui.campo_numero(NS, "frs", "FRS", bm.frs, ctx=bm.id, ajuda="Número, como na lista original.")
    with c:
        po = ui.campo_texto(NS, "po", "PO", bm.po, ctx=bm.id)
    ui.secao("Anexos")
    remover = ui.anexos_remover(NS, bm.anexos, ctx=bm.id)
    novos = ui.campo_anexos(NS, "Adicionar anexos", ctx=bm.id)
    salvar, cancelar = ui.botoes_formulario(True, rotulo_salvar="Salvar")

if salvar:
    ui.executar(
        NS,
        lambda: superus.atualizar_faturamento(
            bm.id, status=status, valor_liberado=valor_liberado, valor_emitido=valor_emitido, mes_referencia=mes,
            frs=frs, po=po, novos_anexos=novos, remover_anexo_ids=remover, versao=lida,
        ),
        "Dados atualizados com sucesso!",
    )
if cancelar:
    ui.reiniciar(NS)
    st.rerun()
