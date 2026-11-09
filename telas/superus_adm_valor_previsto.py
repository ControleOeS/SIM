"""SIM SUPERUS — Administrativo · Valor Previsto (lista SharePoint 'Valor Previsto').

O Controle preenche, para cada mês, quanto se espera medir em cada centro de custo. O gestor vê esse valor ao
lançar o BM mensal, e um BM que fuja mais de 5% dele exige justificativa (sim/services/previsto.py).
Faturamento consulta sem alterar.
"""
import math
from decimal import Decimal

import pandas as pd
import streamlit as st

from sim.auth import principal_atual
from sim.services import previsto
from sim.ui import common as ui

NS = "sup_prev"
PODE_EDITAR = principal_atual().controlador

ui.cabecalho("SUPERUS", "ADM", "Valor Previsto", "Quanto se espera medir em cada centro de custo no mês.")

anos, meses = previsto.anos_e_meses()
f1, f2, _ = st.columns([1, 1, 2], vertical_alignment="bottom")
mes = f1.selectbox("Mês", meses, index=None, placeholder="Selecione", key=ui.chave(NS, "mes"))
ano = f2.selectbox("Ano", anos, index=anos.index("2026") if "2026" in anos else 0, key=ui.chave(NS, "ano"))
if not mes:
    st.info("Escolha o mês para ver e preencher os valores previstos.", icon=":material/touch_app:")
    st.stop()

linhas = ui.carregar(previsto.listar_mes, ano, mes)
tabela = pd.DataFrame(
    [
        {
            "id": cc.id,
            "Centro de Custo": cc.titulo,
            "Obra/Cliente": cc.obra_cliente,
            "Coligada": cc.coligada,
            "Situação": "Ativo" if cc.ativo else "Encerrado",
            "Valor previsto (R$)": None if valor is None else float(valor),
        }
        for cc, valor in linhas
    ]
)
preenchidos = int(tabela["Valor previsto (R$)"].notna().sum()) if len(tabela) else 0
total = sum((v for _, v in linhas if v is not None), Decimal(0))
st.caption(f"{preenchidos} de {len(tabela)} centros de custo com previsto em {mes}/{ano} · total R$ {ui.moeda(total)}")

if PODE_EDITAR:
    st.caption("Digite os valores na última coluna e clique em Salvar. Apague o valor para remover o previsto do CC.")
else:
    st.info("Somente os perfis Controle e Controle Geral alteram o valor previsto. Aqui você apenas consulta.",
            icon=":material/visibility:")

editado = st.data_editor(
    tabela,
    key=ui.chave(NS, "editor", ano, mes),
    hide_index=True,
    width="stretch",
    disabled=not PODE_EDITAR or ["id", "Centro de Custo", "Obra/Cliente", "Coligada", "Situação"],
    column_config={
        "id": None,
        "Valor previsto (R$)": st.column_config.NumberColumn(min_value=0, step=0.01, format="%.2f"),
    },
)

if PODE_EDITAR and st.button("Salvar valores previstos", type="primary", icon=":material/save:"):
    def _decimal(x):
        return None if x is None or (isinstance(x, float) and math.isnan(x)) else Decimal(str(round(float(x), 2)))

    originais = {cc.id: valor for cc, valor in linhas}
    valores = {int(r["id"]): _decimal(r["Valor previsto (R$)"]) for r in editado.to_dict("records")}
    alterados = {k: v for k, v in valores.items() if v != originais.get(k)}
    if not alterados:
        st.info("Nenhum valor foi alterado.", icon=":material/info:")
    else:
        ui.executar(
            NS, lambda: previsto.salvar_mes(ano, mes, alterados),
            f"Valor previsto de {mes}/{ano} atualizado em {len(alterados)} centro(s) de custo.",
        )
ui.resumo_erros(NS, {"ano": "Ano", "mes_referencia": "Mês"})
