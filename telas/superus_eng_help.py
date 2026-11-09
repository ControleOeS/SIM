"""SIM SUPERUS · Central de Ajuda (texto do Label3 original, sem acréscimos)."""
import streamlit as st

from sim.ui import common as ui

ui.cabecalho("SUPERUS", "ENG", "Central de Ajuda", "Glossário do aplicativo original.")

GLOSSARIO = [
    ("NOME DO ARQUIVO", "É a identificação única do seu BM. Utilize um nome que facilite a busca e a referência "
                        "caso você precise editar ou localizar essa medição posteriormente no sistema."),
    ("MÊS DE REFERÊNCIA", "Indica o período de competência do Boletim (mês de fechamento da medição)."),
    ("VALOR BM/PO", "Refere-se ao valor bruto de fechamento da medição antes da validação do cliente. É o valor "
                    "solicitado enquanto o status for 'BM em Análise'."),
    ("GLOSA", "Valor cancelado/'multado' pelo cliente durante o processo de conferência. Valor que não será emitido "
              "em nenhum mês, valor perdido."),
    ("POSTERGADO", "Valor medido que por alguma razão o cliente jogou para o mês seguinte. Valor que será emitido, "
                   "só não vai entrar na competência da quele mês."),
    ("VALOR APROVADO", "É o valor final validado pelo cliente. Atenção: Este campo não se refere à liberação para "
                       "faturamento, mas sim ao montante que o cliente aceitou como medido."),
    ("ANEXO", "Espaço para upload do arquivo do BM (preferencialmente em formato Excel)."),
    ("TIPO", "É a descrição do valor que você estará lançando, se será um BM mensal comum, se será um BM de "
             "cobrança de valores reajustados ou por exemplo um BM de indenização"),
]

for termo, definicao in GLOSSARIO:
    with st.container(border=True):
        st.markdown(f"**{termo}**")
        st.write(definicao)

st.caption("Texto transcrito do aplicativo original. Termos sem definição no original (como Semana, FRS e "
           "Encerramento Manual) não foram acrescentados.")
