"""SIM SUPERUS — Administrativo · Atualizar dados do centro de custo (Gallery2 + Form1).

Correção: o original abria o formulário em modo de inclusão, e "Salvar" sem escolher
uma linha criava um centro de custo vazio. Aqui só é possível editar um CC selecionado.
"""
import streamlit as st

from sim.errors import NotFoundError
from sim.services import superus
from sim.ui import common as ui

NS = "sup_atu"
ROTULOS = {"qtd_bms": "Quantidade de BMs", "cidade": "Cidade", "numero_contrato": "Nº do Contrato"}

ui.cabecalho("SUPERUS", "ADM", "Atualizar dados", "Quantidade de BMs, cidade e número do contrato dos centros de custo.")

ccs = ui.carregar(superus.listar_centros_custo)
st.caption("Clique em uma linha para alterar.")
sel_id = ui.tabela(NS, [
    {"ID": c.id, "Centro de Custo": c.titulo, "Obra/Cliente": c.obra_cliente, "Gestor": c.gestor_obra,
     "Quantidade de BMs sem parada": ui.formatar_numero(c.qtd_bms), "Cidade": c.cidade or "",
     "Nº do Contrato": c.numero_contrato or ""}
    for c in ccs
])

st.divider()
if sel_id is None:
    ui.versao_lida(NS, None)
    st.info("Selecione um centro de custo na tabela para alterar. Esta tela não cria registros.", icon=":material/touch_app:")
    st.stop()
try:
    cc = superus.obter_centro_custo(sel_id)
except NotFoundError as exc:
    st.warning(exc.message)
    ui.reiniciar(NS)
    st.stop()

st.subheader(f"Alterar {cc.titulo} — {cc.obra_cliente}", anchor=False)
lida = ui.versao_lida(NS, cc, cc.id)  # edição simultânea: versão aberta neste formulário
ui.resumo_erros(NS, ROTULOS)
with ui.formulario():
    a, b, c = st.columns(3)
    with a:
        qtd = ui.campo_numero(NS, "qtd_bms", "Quantidade de BMs (Qtd_BMs)", cc.qtd_bms, ctx=cc.id,
                              ajuda="Significado exato a confirmar (a galeria original diz 'Quantidade de BMs sem "
                                    "parada').")
    with b:
        cidade = ui.campo_texto(NS, "cidade", "Cidade", cc.cidade, ctx=cc.id)
    with c:
        contrato = ui.campo_texto(NS, "numero_contrato", "Nº do Contrato", cc.numero_contrato, ctx=cc.id)
    salvar, cancelar = ui.botoes_formulario(True, rotulo_salvar="Salvar")

if salvar:
    ui.executar(
        NS,
        lambda: superus.atualizar_dados_cc(
            cc.id, qtd_bms=qtd, cidade=cidade, numero_contrato=contrato, versao=lida
        ),
        f"Dados do centro de custo {cc.titulo} atualizados.",
    )
if cancelar:
    ui.reiniciar(NS)
    st.rerun()
