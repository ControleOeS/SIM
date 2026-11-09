"""SIM SUPERUS — Administrativo · Planejamento (consulta de BMs mensais e semanais)."""
import streamlit as st

from sim.options import opcoes
from sim.services import superus
from sim.ui import common as ui

ui.cabecalho("SUPERUS", "ADM", "Planejamento", "Consulta dos BMs mensais e semanais. Somente leitura.")

ccs = ui.carregar(superus.listar_centros_custo)
cc_por_id = {c.id: c for c in ccs}
meses = list(opcoes("superus.mes_referencia").valores)

aba_m, aba_s = st.tabs(["Mensal", "Semanal"])

with aba_m:
    f1, f2, f3 = st.columns([1.3, 1, 0.6], vertical_alignment="bottom")
    cc_m = f1.selectbox("Centro de Custo", list(cc_por_id), index=None, placeholder="Todos",
                        format_func=lambda i: cc_por_id[i].titulo, key=ui.chave("plan_m", "cc"))
    mes_m = f2.selectbox("Mês", meses, index=None, placeholder="Todos", key=ui.chave("plan_m", "mes"))
    if f3.button("Limpar", key="plan_m_limpar", width="stretch", icon=ui.ICONE["filtro_limpar"]):
        ui.reiniciar("plan_m")
        st.rerun()
    bms = ui.carregar(superus.listar_bms_mensais, centro_custo_id=cc_m, mes=mes_m)
    st.caption(f"{len(bms)} BM(s) mensal(is)")
    ui.tabela("plan_m", [
        {"ID": b.id, "Centro de Custo": b.centro_custo.titulo, "Mês": b.mes_referencia, "Ano": b.ano,
         "Nome do Arquivo": b.titulo, "Valor BM/PO": ui.moeda(b.valor_bm),
         "Valor Aprovado": ui.moeda(b.valor_aprovado), "Status": b.status, "Anexos": ui.qtd_anexos(b.anexos)}
        for b in bms
    ], selecionavel=False)

with aba_s:
    f1, f2, f3, f4 = st.columns([1.3, 1, 1, 0.6], vertical_alignment="bottom")
    cc_s = f1.selectbox("Centro de Custo", list(cc_por_id), index=None, placeholder="Todos",
                        format_func=lambda i: cc_por_id[i].titulo, key=ui.chave("plan_s", "cc"))
    mes_s = f2.selectbox("Mês", meses, index=None, placeholder="Todos", key=ui.chave("plan_s", "mes"))
    sem_s = f3.selectbox("Semana", list(opcoes("superus.semana").valores), index=None, placeholder="Todas",
                         key=ui.chave("plan_s", "sem"))
    if f4.button("Limpar", key="plan_s_limpar", width="stretch", icon=ui.ICONE["filtro_limpar"]):
        ui.reiniciar("plan_s")
        st.rerun()
    sems = ui.carregar(superus.listar_bms_semanais, centro_custo_id=cc_s, mes=mes_s, semana=sem_s)
    st.caption(f"{len(sems)} BM(s) semanal(is)")
    ui.tabela("plan_s", [
        {"ID": b.id, "Centro de Custo": b.centro_custo.titulo, "Mês": b.mes_referencia, "Semana": b.semana,
         "Nome do Arquivo": b.titulo, "Valor Acumulado do BM": ui.moeda(b.valor_bm),
         "Anexos": ui.qtd_anexos(b.anexos)}
        for b in sems
    ], selecionavel=False)
