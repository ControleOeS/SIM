"""SIM ASAP — Engenharia · BM Mensal (Gallery1 + Form1 do original)."""
import streamlit as st

from sim.errors import NotFoundError
from sim.options import opcoes
from sim.services import asap
from sim.ui import common as ui
from sim.ui.common import ICONE

NS = "asap_bm"
P = st.session_state["_paginas"]
ROTULOS = {
    "centro_custo_id": "Centro de Custo", "titulo": "Nome do Arquivo", "ano": "Ano",
    "mes_referencia": "Mês de Referência", "status": "Status", "valor_bm": "Valor BM",
    "valor_aprovado": "Valor Aprovado", "glosa": "Glosa", "observacoes": "Observações", "anexos": "Anexos",
}

ui.cabecalho("ASAP", "ENG", "BM Mensal", "Boletins de medição mensais da ASAP.")

ccs = ui.carregar(asap.listar_centros_custo)
if not ccs:
    st.warning("Nenhum centro de custo cadastrado. Cadastre um antes de lançar BMs.", icon=":material/info:")
    if "asap_cc" in P:
        st.page_link(P["asap_cc"], label="Ir para Cadastro Centro de Custo", icon=":material/sell:")
    st.stop()

cc_por_id = {c.id: c for c in ccs}


def rotulo_cc(i: int) -> str:
    c = cc_por_id.get(i)
    if c is None:
        return f"(CC {i} não encontrado)"
    return f"{c.titulo} — {c.cliente}" + ("" if c.ativo else " · ENCERRADO")


# 1. "Escolha seu Centro de Custos" (RN-02). OK exige seleção (P-07).
cc_padrao = st.session_state.get("asap_cc_padrao")
if cc_padrao not in cc_por_id or st.session_state.get("asap_trocar_cc"):
    with st.container(border=True):
        st.subheader("Escolha seu Centro de Custos", anchor=False)
        st.caption("Ele será o padrão dos novos BMs. Digite para buscar pelo título ou pelo cliente.")
        escolha = st.selectbox("Centro de custo", list(cc_por_id), format_func=rotulo_cc, index=None,
                               placeholder="Selecione")
        if st.button("OK", type="primary", disabled=escolha is None, icon=ICONE["ok"]):
            st.session_state["asap_cc_padrao"] = escolha
            st.session_state["asap_trocar_cc"] = False
            ui.reiniciar(NS)
            st.rerun()
    st.stop()

with st.container(border=True):
    c1, c2 = st.columns([4, 1.2], vertical_alignment="center")
    c1.markdown(f":material/sell: Centro de custo padrão para novos BMs: **{rotulo_cc(cc_padrao)}**")
    if c2.button("Trocar centro de custo", width="stretch", icon=ICONE["trocar"]):
        st.session_state["asap_trocar_cc"] = True
        st.rerun()

# 2. Lista: todos os BMs, ID decrescente (RN-01)
bms = ui.carregar(asap.listar_bms)
st.subheader(f"BMs lançados ({len(bms)})", anchor=False)
st.caption("Clique em uma linha para editar ou excluir o BM.")
sel_id = ui.tabela(NS, [
    {
        "ID": b.id,
        "Centro de Custo": b.centro_custo.titulo,
        "Nome do Arquivo": b.titulo,
        "Ano": b.ano,
        "Mês do BM": b.mes_referencia,
        "Valor do BM": ui.moeda(b.valor_bm),
        "Valor Emitido": ui.moeda(b.valor_emitido),
        "Valor Aprovado": ui.moeda(b.valor_aprovado),
        "Status": b.status,
        "Anexos": ui.qtd_anexos(b.anexos),
        "Data Criação": ui.data_hora(b.criado_em),
    }
    for b in bms
])

bm = None
if sel_id is not None:
    try:
        bm = asap.obter_bm(sel_id)
    except NotFoundError as exc:
        st.warning(exc.message)
        ui.reiniciar(NS)

# 3. Formulário
st.divider()
editando = bm is not None
ctx = bm.id if editando else "novo"
lida = ui.versao_lida(NS, bm, ctx)  # edição simultânea: versão aberta neste formulário
st.subheader(f"Editar BM #{bm.id}" if editando else "Novo BM", anchor=False)
if editando:
    info = f"Valor Emitido (preenchido pelo Administrativo): **{ui.moeda(bm.valor_emitido) or '—'}**"
    if bm.data_aprovacao_cliente:
        info += f" · Aprovado pelo cliente em **{ui.data_hora(bm.data_aprovacao_cliente)}**"
    st.markdown(info)
    ui.anexos_download(NS, bm.anexos, ctx=ctx)

if not editando and not any(c.ativo for c in cc_por_id.values()):
    st.warning("Todos os centros de custo disponíveis estão encerrados; não é possível lançar novos BMs.",
               icon=":material/block:")
    st.stop()
if not editando and not cc_por_id[cc_padrao].ativo:
    st.warning(f"O centro de custo padrão ({cc_por_id[cc_padrao].titulo}) está encerrado. Escolha outro no formulário.",
               icon=":material/block:")

ui.resumo_erros(NS, ROTULOS)
with ui.formulario():
    cc_inicial = bm.centro_custo_id if editando else cc_padrao  # P-01: na edição, o CC do próprio registro
    # Novos BMs (ou mudança de CC) só em centros ativos; o CC atual do BM sempre aparece.
    ids_cc = [i for i, c in cc_por_id.items() if c.ativo or (editando and i == bm.centro_custo_id)]
    if editando and bm.centro_custo_id not in cc_por_id:
        ids_cc.insert(0, bm.centro_custo_id)
    if cc_inicial not in ids_cc:
        cc_inicial = ids_cc[0]

    ui.secao("Identificação")
    a, b_ = st.columns(2)
    with a:
        centro = st.selectbox("Centro de Custo *", ids_cc, index=ids_cc.index(cc_inicial), format_func=rotulo_cc,
                              key=ui.chave(NS, "centro_custo_id", ctx))
        ui.erro_campo(NS, "centro_custo_id")
    with b_:
        titulo = ui.campo_texto(NS, "titulo", "Nome do Arquivo", bm.titulo if editando else "", obrigatorio=True,
                                ctx=ctx)
    a, b_, c = st.columns(3)
    with a:
        ano = ui.campo_escolha(NS, "ano", "Ano", opcoes("asap.ano"), bm.ano if editando else None,
                               obrigatorio=True, ctx=ctx)
    with b_:
        mes = ui.campo_escolha(NS, "mes_referencia", "Mês de Referência", opcoes("asap.mes_referencia"),
                               bm.mes_referencia if editando else None, obrigatorio=True, ctx=ctx)
    with c:
        status = ui.campo_escolha(NS, "status", "Status", opcoes("asap.status"), bm.status if editando else None,
                                  obrigatorio=True, ctx=ctx)

    ui.secao("Valores (R$)")
    a, b_, c = st.columns(3)
    with a:
        valor_bm = ui.campo_moeda(NS, "valor_bm", "Valor BM", bm.valor_bm if editando else None, obrigatorio=True,
                                  ctx=ctx)
    with b_:
        valor_aprovado = ui.campo_moeda(
            NS, "valor_aprovado", "Valor Aprovado", bm.valor_aprovado if editando else None, obrigatorio=True,
            ajuda="⚠ Caso ainda não tenha sido aprovado, preencha com 0", ctx=ctx,
        )
    with c:
        glosa = ui.campo_moeda(NS, "glosa", "Glosa", bm.glosa if editando else None, ctx=ctx)
    st.caption("⚠ Valor Aprovado: caso ainda não tenha sido aprovado, preencha com 0.")

    ui.secao("Observações e anexos")
    observacoes = ui.campo_texto(NS, "observacoes", "Observações", bm.observacoes if editando else "", area=True,
                                 max_chars=None, ctx=ctx)
    remover = ui.anexos_remover(NS, bm.anexos, ctx=ctx) if editando else []
    novos = ui.campo_anexos(NS, "Adicionar anexos" if editando else "Anexos", obrigatorio=not editando, ctx=ctx)

    salvar, cancelar = ui.botoes_formulario(editando)

dados = {
    "centro_custo_id": centro, "titulo": titulo, "ano": ano, "mes_referencia": mes, "status": status,
    "valor_bm": valor_bm, "valor_aprovado": valor_aprovado, "glosa": glosa, "observacoes": observacoes,
}
if salvar:
    if editando:
        ui.executar(NS, lambda: asap.atualizar_bm(bm.id, dados, novos, remover, versao=lida), f"BM #{bm.id} atualizado.")
    else:
        ui.executar(NS, lambda: asap.criar_bm(dados, novos), "BM cadastrado com sucesso.")
if cancelar:
    ui.reiniciar(NS)
    st.rerun()

if editando and ui.botao_excluir(NS, "Excluir este BM", bm.id):
    ui.confirmar_exclusao(
        NS, f"BM **#{bm.id} — {bm.titulo}** ({bm.centro_custo.titulo}, {bm.mes_referencia}/{bm.ano})",
        lambda: asap.excluir_bm(bm.id, versao=lida), f"BM #{bm.id} excluído.",
    )
