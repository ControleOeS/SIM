"""Valor previsto (SUPERUS): quanto se espera medir em cada centro de custo no mês.

Regras (decisão do responsável em 2026-10-27):
- Quem preenche são os perfis Controle e Controle Geral, no Administrativo. Faturamento só consulta.
- O gestor vê o previsto do mês ao lançar o BM mensal.
- Se o valor do BM ficar mais de 5% acima ou abaixo do previsto, o BM exige uma justificativa: acima, qual foi a
  boa estratégia utilizada; abaixo, quais problemas fizeram o valor fugir do refinado anterior.
- A comparação é do valor de cada BM com o previsto do CC no mês. Previsto zero com BM acima de zero também
  exige justificativa. A regra vale ao criar o BM e, na edição, só quando valor, mês ou ano mudam.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from sim.auth import exigir_area_adm, exigir_centro, exigir_controlador
from sim.formatters import formatar_moeda, formatar_numero
from sim.models import SuperusCentroCusto, SuperusValorPrevisto
from sim.options import opcoes
from sim.services.common import Validador, leitura, transacao

EMPRESA = "SUPERUS"
TOLERANCIA = Decimal("0.05")
CAMPO_JUSTIFICATIVA = "justificativa_variacao"


def previsto_de(session: Session, centro_custo_id: int, ano: str | None, mes: str | None) -> Decimal | None:
    if not ano or not mes:
        return None
    return session.scalar(
        select(SuperusValorPrevisto.valor).where(
            SuperusValorPrevisto.centro_custo_id == centro_custo_id,
            SuperusValorPrevisto.ano == ano,
            SuperusValorPrevisto.mes_referencia == mes,
        )
    )


def obter(centro_custo_id: int, ano: str | None, mes: str | None) -> Decimal | None:
    """Previsto do CC no mês, para o formulário do BM (quem vê o CC vê o previsto dele)."""
    exigir_centro(EMPRESA, centro_custo_id)
    with leitura() as s:
        return previsto_de(s, centro_custo_id, ano, mes)


def variacao(valor: Decimal | None, previsto: Decimal | None) -> Decimal | None:
    """Variação relativa do BM sobre o previsto (0,10 = 10% acima). None sem previsto ou sem valor."""
    if valor is None or previsto is None:
        return None
    if previsto == 0:
        return None if valor == 0 else Decimal("Infinity")
    return (valor - previsto) / previsto


def fora_da_tolerancia(valor: Decimal | None, previsto: Decimal | None) -> bool:
    v = variacao(valor, previsto)
    return v is not None and abs(v) > TOLERANCIA


def pergunta(valor: Decimal, previsto: Decimal) -> str:
    """O que o gestor precisa explicar, conforme o BM ficou acima ou abaixo do previsto."""
    v = variacao(valor, previsto)
    base = f"valor previsto (R$ {formatar_moeda(previsto)})"
    if v is None or v > 0:
        quanto = "acima do" if v is None or v.is_infinite() else f"{formatar_numero(round(v * 100, 1))}% acima do"
        return (f"O valor do BM ficou {quanto} {base}. Explique por que ultrapassou o previsto em mais de 5%: "
                "qual foi a boa estratégia utilizada?")
    return (f"O valor do BM ficou {formatar_numero(round(-v * 100, 1))}% abaixo do {base}. Explique por que ficou "
            "mais de 5% abaixo do previsto: quais problemas enfrentados fizeram o valor fugir do refinado anterior?")


def conferir_variacao(v: Validador, previsto: Decimal | None) -> None:
    """Acrescenta ao validador o erro de justificativa faltante e deixa nos valores o previsto usado.

    Dentro da tolerância (ou sem previsto), a justificativa é descartada."""
    valor = v.valores.get("valor_bm")
    v.valores["valor_previsto"] = previsto
    if not fora_da_tolerancia(valor, previsto):  # type: ignore[arg-type]
        v.valores[CAMPO_JUSTIFICATIVA] = None
    elif not v.valores.get(CAMPO_JUSTIFICATIVA):
        v.erro(CAMPO_JUSTIFICATIVA, pergunta(valor, previsto))  # type: ignore[arg-type]


# ------------------------------------------------------- Administrativo ----


def listar_mes(ano: str, mes: str) -> list[tuple[SuperusCentroCusto, Decimal | None]]:
    """Todos os CCs com o previsto do mês (None quando ainda não foi preenchido). Ativos primeiro."""
    exigir_area_adm()
    with leitura() as s:
        centros = s.scalars(select(SuperusCentroCusto).order_by(SuperusCentroCusto.titulo)).all()
        valores = dict(
            s.execute(
                select(SuperusValorPrevisto.centro_custo_id, SuperusValorPrevisto.valor).where(
                    SuperusValorPrevisto.ano == ano, SuperusValorPrevisto.mes_referencia == mes
                )
            ).all()
        )
        return sorted(((c, valores.get(c.id)) for c in centros), key=lambda par: not par[0].ativo)


def salvar_mes(ano: str, mes: str, valores: dict[int, object]) -> int:
    """Grava o previsto de vários CCs no mês. Valor vazio apaga o previsto do CC. Devolve quantos mudaram."""
    exigir_controlador()
    v = Validador()
    v.escolha("ano", ano, opcoes("superus.ano").valores, obrigatorio=True)
    v.escolha("mes_referencia", mes, opcoes("superus.mes_referencia").valores, obrigatorio=True)
    for cc_id, valor in valores.items():
        v.moeda(f"cc_{cc_id}", valor)
    lidos = v.verificar()
    alterados = 0
    with transacao("previsto.salvar_mes") as tx:
        s = tx.session
        existentes: dict[int, SuperusValorPrevisto] = {
            p.centro_custo_id: p
            for p in s.scalars(
                select(SuperusValorPrevisto).where(
                    SuperusValorPrevisto.ano == ano,
                    SuperusValorPrevisto.mes_referencia == mes,
                    SuperusValorPrevisto.centro_custo_id.in_(list(valores)),
                )
            )
        }
        for cc_id in valores:
            novo: Decimal | None = lidos[f"cc_{cc_id}"]  # type: ignore[assignment]
            atual = existentes.get(cc_id)
            if novo is None and atual is not None:
                s.delete(atual)
            elif novo is not None and atual is None:
                if s.get(SuperusCentroCusto, cc_id) is None:
                    continue
                s.add(SuperusValorPrevisto(centro_custo_id=cc_id, ano=ano, mes_referencia=mes, valor=novo))
            elif novo is not None and atual is not None and atual.valor != novo:
                atual.valor = novo
            else:
                continue
            alterados += 1
    return alterados


def anos_e_meses() -> tuple[Sequence[str], Sequence[str]]:
    return list(opcoes("superus.ano").valores), list(opcoes("superus.mes_referencia").valores)
