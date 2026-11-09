"""SIM ASAP — Administrativo · Faturamento (Gallery5 + Form2 do original).

Correção: o formulário só grava sobre um BM selecionado; não existe modo de inclusão.
"""
import streamlit as st

from sim.errors import NotFoundError
from sim.services import asap
from sim.ui import common as ui

NS = "asap_fat"
NSF = "asap_fat_filtros"
ROTULOS = {"valor_emitido": "Valor Emitido", "status": "Status", "anexos": "Anexos"}

ui.cabecalho("ASAP", "ADM", "Faturamento", "Conferência dos BMs e registro do faturamento.")

op = ui.carregar(asap.opcoes_filtro_faturamento)
cc_por_id = {c.id: c for c in op["centros"]}

with st.container(border=True):
    ui.secao("Filtros")
    f1, f2, f3, f4 = st.columns([1, 1, 1.4, 0.6], vertical_alignment="bottom")
    mes = f1.selectbox("Mês", op["meses"], index=None, placeholder="Todos", key=ui.chave(NSF, "mes"))
    status = f2.selectbox("Status", op["status"], index=None, placeholder="Todos", key=ui.chave(NSF, "status"))
    cc_id = f3.selectbox("Centro de Custo", list(cc_por_id), index=None, placeholder="Todos",
                         format_func=lambda i: cc_por_id[i].titulo, key=ui.chave(NSF, "cc"))
    if f4.button("Limpar filtros", width="stretch", icon=ui.ICONE["filtro_limpar"]):
        ui.reiniciar(NSF)
        ui.reiniciar(NS)
        st.rerun()

bms = ui.carregar(asap.listar_bms, centro_custo_id=cc_id, mes=mes, status=status)
st.subheader(f"BMs ({len(bms)})", anchor=False)
st.caption("Clique em uma linha para alterar Valor Emitido, Status ou Anexos. O filtro de mês não considera o ano, "
           "como no original.")
sel_id = ui.tabela(NS, [
    {
        "ID": b.id,
        "Centro de Custo": b.centro_custo.titulo,
        "Cliente": b.centro_custo.cliente,
        "Nome do Arquivo": b.titulo,
        "Ano": b.ano,
        "Mês": b.mes_referencia,
        "Valor BM": ui.moeda(b.valor_bm),
        "Valor Aprovado": ui.moeda(b.valor_aprovado),
        "Valor Emitido": ui.moeda(b.valor_emitido),
        "Glosa": ui.moeda(b.glosa),
        "Período": b.centro_custo.periodo or "",
        "Status": b.status,
        "Anexos": ui.qtd_anexos(b.anexos),
        "Data Criação": ui.data_hora(b.criado_em),
        "Observação": b.observacoes or "",
    }
    for b in bms
], ctx=(mes, status, cc_id))

st.divider()
if sel_id is None:
    ui.versao_lida(NS, None)
    st.info("Selecione um BM na tabela para alterar. Esta tela não cria BMs.", icon=":material/touch_app:")
    st.stop()

try:
    bm = asap.obter_bm(sel_id)
except NotFoundError as exc:
    st.warning(exc.message)
    ui.reiniciar(NS)
    st.stop()

st.subheader(f"Alterar BM #{bm.id} — {bm.titulo}", anchor=False)
lida = ui.versao_lida(NS, bm, bm.id)  # edição simultânea: versão aberta neste formulário
ui.secao("Dados da engenharia (somente consulta)")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Centro de Custo", bm.centro_custo.titulo)
c2.metric("Referência", f"{bm.mes_referencia}/{bm.ano}")
c3.metric("Valor BM", ui.moeda(bm.valor_bm) or "—")
c4.metric("Valor Aprovado", ui.moeda(bm.valor_aprovado) or "—")
ui.anexos_download(NS, bm.anexos, ctx=bm.id)
ui.resumo_erros(NS, ROTULOS)
with ui.formulario():
    ui.secao("Faturamento")
    a, b = st.columns(2)
    with a:
        valor_emitido = ui.campo_moeda(NS, "valor_emitido", "Valor Emitido", bm.valor_emitido, ctx=bm.id)
    with b:
        novo_status = ui.campo_escolha(
            NS, "status", "Status", asap.status_permitidos_faturamento(bm.status), bm.status, obrigatorio=True,
            ctx=bm.id, ajuda="Como no original: manter o status atual ou marcar como 'Faturado Total'.",
        )
    ui.secao("Anexos")
    remover = ui.anexos_remover(NS, bm.anexos, ctx=bm.id)
    novos = ui.campo_anexos(NS, "Adicionar anexos", ctx=bm.id)
    salvar, cancelar = ui.botoes_formulario(True, rotulo_salvar="Salvar")

if salvar:
    ui.executar(
        NS,
        lambda: asap.atualizar_faturamento(bm.id, valor_emitido=valor_emitido, status=novo_status,
                                           novos_anexos=novos, remover_anexo_ids=remover, versao=lida),
        "Dados atualizados com sucesso!",
    )
if cancelar:
    ui.reiniciar(NS)
    st.rerun()
