"""Importação do histórico do SIM antigo (Power Apps / listas SharePoint da SUPERUS).

Lê as exportações em Excel das listas ("Base <lista> Lists.xlsx") e grava no banco configurado:

- Lista de Apoio      -> superus_centros_custo (casados pelo código do CC, o Title)
- BMs                 -> superus_bms_mensais   (id_legado = ID do item)
- BM Semanal          -> superus_bms_semanais  (id_legado = ID do item)
- Valor Previsto      -> superus_valores_previstos (ano 2026: a lista não tem coluna de ano)
- Historico BMs       -> só consulta: recupera o CC de BMs cujo vínculo se perdeu na lista atual

Não importa: as listas de histórico como
registros (são versões de cada edição; BMs que só existem nelas foram excluídos no original) e os
anexos (não vêm na exportação). BMs importados ficam sem anexo e podem ser editados mesmo assim.

Repetível: CC já cadastrado e BM com o mesmo id_legado são mantidos como estão, sem sobrescrever o
que foi alterado no SIM novo. Sem --aplicar, só mostra o relatório (nada é gravado).

Executar:  python -m sim.importacao_legado <pasta com as planilhas> [--aplicar]
"""
from __future__ import annotations

import argparse
import math
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, update

from sim.bootstrap import inicializar
from sim.database import session_scope
from sim.formatters import normalizar_chave
from sim.models import (
    Empresa,
    EncerramentoCentroCusto,
    SuperusBMMensal,
    SuperusBMSemanal,
    SuperusCentroCusto,
    SuperusValorPrevisto,
)
from sim.services.superus import COLIGADAS, EMPRESA

# Os horários exportados estão no fuso de Brasília (os lançamentos caem no horário de expediente,
# com a pausa do almoço às 12h); o banco guarda UTC.
DESLOCAMENTO_UTC = timedelta(hours=3)
COLIGADAS_TESTE = {"o&s"}  # CC "1 - Cliente X Y Z", usado para testes no original
JUSTIFICATIVA_IMPORTADA = "Encerrado no SIM antigo (importação do histórico)."
ANO_PREVISTO = "2026"  # a lista Valor Previsto só tem o mês; todos os itens são de 2026


# ---------------------------------------------------------------- leitura ----


def _ler(pasta: Path, lista: str):
    import pandas as pd

    caminho = pasta / f"Base {lista} Lists.xlsx"
    if not caminho.exists():
        raise SystemExit(f"Arquivo não encontrado: {caminho}")
    df = pd.read_excel(caminho)
    df.columns = [unicodedata.normalize("NFC", str(c)).replace("\xa0", " ").strip() for c in df.columns]
    return df.astype(object).where(df.notna(), None).to_dict("records")


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor)) or (isinstance(valor, str) and not valor.strip())


def _texto(valor) -> str | None:
    if _vazio(valor):
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return " ".join(str(valor).split())


def _inteiro(valor) -> int | None:
    return None if _vazio(valor) else int(float(valor))


def _dinheiro(valor) -> Decimal | None:
    return None if _vazio(valor) else Decimal(str(round(float(valor), 2)))


def _numero(valor) -> Decimal | None:
    return None if _vazio(valor) else Decimal(str(float(valor))).normalize()


def _data(valor) -> date | None:
    return None if _vazio(valor) else valor.date() if isinstance(valor, datetime) else valor


def _utc(valor) -> datetime | None:
    return None if _vazio(valor) else valor.to_pydatetime().replace(tzinfo=None) + DESLOCAMENTO_UTC


# ------------------------------------------------------------- relatório ----


@dataclass
class Relatorio:
    contagem: Counter = field(default_factory=Counter)
    avisos: list[str] = field(default_factory=list)
    ignorados: list[str] = field(default_factory=list)

    def imprimir(self, aplicado: bool) -> None:
        print("IMPORTAÇÃO GRAVADA" if aplicado else "SIMULAÇÃO (nada foi gravado; use --aplicar para gravar)")
        for chave, n in sorted(self.contagem.items()):
            print(f"  {chave}: {n}")
        if self.avisos:
            print("\nAvisos (conferir):")
            for a in self.avisos:
                print(f"  - {a}")
        if self.ignorados:
            print("\nNão importados:")
            for a in self.ignorados:
                print(f"  - {a}")


# ------------------------------------------------------- centros de custo ----


def _coligada(valor) -> str | None:
    texto = (_texto(valor) or "").upper()
    return texto if texto in COLIGADAS else None


def _cliente(item: dict) -> str:
    return ((_texto(item["Obra/Cliente"]) or "").split() or [""])[0].casefold()


def _inferir_coligadas(apoio: list[dict], rel: Relatorio) -> dict[str, str]:
    """Coligada de cada CC. Sem coligada na lista, usa a dos outros CCs do mesmo cliente
    (primeira palavra de Obra/Cliente), desde que todos concordem."""
    por_cliente: dict[str, set[str]] = defaultdict(set)
    resultado: dict[str, str] = {}
    for item in apoio:
        coligada = _coligada(item["Coligada"])
        if coligada:
            resultado[_texto(item["Title"])] = coligada
            por_cliente[_cliente(item)].add(coligada)
    for item in apoio:
        codigo = _texto(item["Title"])
        if codigo in resultado or (_texto(item["Coligada"]) or "").casefold() in COLIGADAS_TESTE:
            continue
        cliente = _cliente(item)
        candidatas = por_cliente.get(cliente, set())
        if len(candidatas) == 1:
            resultado[codigo] = next(iter(candidatas))
            rel.avisos.append(
                f"CC {codigo} ({_texto(item['Obra/Cliente'])}) estava sem coligada; "
                f"assumida {resultado[codigo]}, a mesma dos outros CCs desse cliente."
            )
    return resultado


def _importar_centros(session, apoio: list[dict], rel: Relatorio) -> dict[str, SuperusCentroCusto]:
    empresa_id = session.scalar(select(Empresa.id).where(Empresa.codigo == EMPRESA))
    coligadas = _inferir_coligadas(apoio, rel)
    centros: dict[str, SuperusCentroCusto] = {}
    for item in apoio:
        codigo = _texto(item["Title"])
        descricao = f"CC {codigo} ({_texto(item['Obra/Cliente'])})"
        if (_texto(item["Coligada"]) or "").casefold() in COLIGADAS_TESTE:
            rel.ignorados.append(f"{descricao}: centro de custo de teste (coligada O&S), com os BMs dele.")
            continue
        if codigo not in coligadas:
            rel.ignorados.append(f"{descricao}: sem coligada e sem como deduzir.")
            continue
        existente = session.scalar(
            select(SuperusCentroCusto).where(SuperusCentroCusto.titulo_chave == normalizar_chave(codigo))
        )
        if existente:
            centros[codigo] = existente
            rel.contagem["Centros de custo já existentes (mantidos)"] += 1
            continue
        encerrado = _texto(item["EncerramentoManual"]) in ("True", "Sim", "1")
        novo_prazo = _inteiro(item["Novo prazo"])
        cc = SuperusCentroCusto(
            empresa_id=empresa_id,
            titulo=codigo,
            titulo_chave=normalizar_chave(codigo),
            obra_cliente=_texto(item["Obra/Cliente"]),
            gestor_obra=_texto(item["Gestor de Obra"]) or "",
            coligada=coligadas[codigo],
            numero_contrato=_texto(item["Nº do Contrato"]),
            cidade=_texto(item["Cidade"]),
            inicio_medicao=_numero(item["Inicio de Medição"]),
            fim_medicao=_numero(item["Fim de Medição"]),
            meta_bm=_numero(item["Meta BM"]),
            meta_frs=_numero(item["Meta FRS"]),
            novo_prazo=None if novo_prazo is None else bool(novo_prazo),
            competencia_emissao=_texto(item["Competência de Emissão"]),
            email_gestor=_texto(item["Email"]),
            email_gerente=_texto(item["Email Gerente"]),
            gerente=_texto(item["Gerente"]),
            status_cobranca=_texto(item["StatusCobrança"]),
            encerramento_manual="Sim" if encerrado else None,
            qtd_bms=_numero(item["Qtd_BMs"]),
            mes_apuracao=_data(item["Mês de Apuração"]),
            motivo_encerramento=_texto(item["Motivo Encerramento"]),
            ativo=not encerrado,
        )
        session.add(cc)
        session.flush()
        centros[codigo] = cc
        rel.contagem["Centros de custo importados"] += 1
        if encerrado:
            session.add(
                EncerramentoCentroCusto(
                    empresa_id=empresa_id,
                    superus_cc_id=cc.id,
                    acao="encerrar",
                    status="aprovada",
                    justificativa=cc.motivo_encerramento or JUSTIFICATIVA_IMPORTADA,
                    parecer=JUSTIFICATIVA_IMPORTADA,
                    decidido_em=cc.criado_em,
                )
            )
            rel.avisos.append(
                f"{descricao} estava com Encerramento Manual no SIM antigo: importado como encerrado "
                "(não aceita novos BMs; reative em Encerramento se ainda estiver em uso)."
            )
    return centros


# -------------------------------------------------------------------- BMs ----


def _cc_recuperado(item: dict, historico: dict[int, str], por_contrato: dict[str, set[str]], centros: dict) -> str | None:
    """CC de um BM cujo vínculo veio vazio: primeiro pelo histórico de versões do próprio BM,
    depois pelo número do contrato, se ele pertencer a um único CC importado."""
    if item["ID"] in historico:
        return historico[item["ID"]]
    candidatos = por_contrato.get(_texto(item["Nº do Contrato"]) or "", set()) & centros.keys()
    return next(iter(candidatos)) if len(candidatos) == 1 else None


def _importar_mensais(session, bms: list[dict], hist: list[dict], centros: dict, rel: Relatorio) -> None:
    historico: dict[int, str] = {}
    for h in sorted(hist, key=lambda h: h["ID"]):
        if not _vazio(h["Integração"]):
            historico[h["ID Original"]] = _texto(h["Integração"])
    por_contrato: dict[str, set[str]] = defaultdict(set)
    for item in bms:
        if not _vazio(item["Integração"]) and _texto(item["Nº do Contrato"]):
            por_contrato[_texto(item["Nº do Contrato"])].add(_texto(item["Integração"]))
    existentes = set(session.scalars(select(SuperusBMMensal.id_legado).where(SuperusBMMensal.id_legado.is_not(None))))

    for item in bms:
        ref = f"BM mensal ID {item['ID']} ({_texto(item['Title']) or 'sem título'})"
        if item["ID"] in existentes:
            rel.contagem["BMs mensais já importados (mantidos)"] += 1
            continue
        if _vazio(item["Valor BM"]) or _vazio(item["Mês de Referência"]):
            rel.ignorados.append(f"{ref}: registro vazio (sem valor e sem mês).")
            continue
        codigo = _texto(item["Integração"])
        if codigo is None:
            codigo = _cc_recuperado(item, historico, por_contrato, centros)
            if codigo:
                rel.avisos.append(f"{ref}: estava sem centro de custo; vinculado ao CC {codigo} pelo histórico/contrato.")
        if codigo not in centros:
            rel.ignorados.append(f"{ref}: centro de custo {codigo or 'não informado'} não importado.")
            continue
        if _vazio(item["Cidade"]) or _vazio(item["Nº do Contrato"]):
            rel.contagem["BMs mensais sem cidade/contrato (ficam em branco)"] += 1
        session.add(
            SuperusBMMensal(
                id_legado=item["ID"],
                centro_custo_id=centros[codigo].id,
                titulo=_texto(item["Title"]) or "(sem título)",
                numero_contrato=_texto(item["Nº do Contrato"]) or "",
                cidade=_texto(item["Cidade"]) or "",
                ano=_texto(item["Ano"]),
                mes_referencia=_texto(item["Mês de Referência"]),
                tipo=_texto(item["Tipo1"]) or "BM",
                status=_texto(item["Status"]),
                valor_bm=_dinheiro(item["Valor BM"]),
                glosa=_dinheiro(item["Glosa"]),
                postergado=_dinheiro(item["Postergado"]),
                valor_aprovado=_dinheiro(item["Valor Aprovado"]),
                valor_liberado=_dinheiro(item["Valor Liberado"]),
                valor_emitido=_dinheiro(item["Valor Emitido"]),
                frs=_numero(item["FRS"]),
                po=_texto(item["PO"]),
                prazo_envio_bm=_data(item["Prazo Envio BM"]),
                prazo_liberacao_frs=_data(item["Prazo Liberação FRS"]),
                data_faturamento=_data(item["Data de Faturamento"]),
                criado_em=_utc(item["Created"]),
                atualizado_em=_utc(item["Modified"]),
            )
        )
        rel.contagem["BMs mensais importados"] += 1


def _importar_semanais(session, semanais: list[dict], centros: dict, rel: Relatorio) -> None:
    existentes = set(
        session.scalars(select(SuperusBMSemanal.id_legado).where(SuperusBMSemanal.id_legado.is_not(None)))
    )
    for item in semanais:
        ref = f"BM semanal ID {item['ID']} ({_texto(item['Title']) or 'sem título'})"
        if item["ID"] in existentes:
            rel.contagem["BMs semanais já importados (mantidos)"] += 1
            continue
        codigo = _texto(item["Integração2"])
        if codigo not in centros:
            rel.ignorados.append(f"{ref}: centro de custo {codigo or 'não informado'} não importado.")
            continue
        if _vazio(item["Valor do BM"]) or _vazio(item["Mês de Referência"]) or _vazio(item["Semana"]):
            rel.ignorados.append(f"{ref}: sem valor, mês ou semana.")
            continue
        session.add(
            SuperusBMSemanal(
                id_legado=item["ID"],
                centro_custo_id=centros[codigo].id,
                titulo=_texto(item["Title"]) or "(sem título)",
                mes_referencia=_texto(item["Mês de Referência"]),
                semana=_texto(item["Semana"]),
                valor_bm=_dinheiro(item["Valor do BM"]),
                criado_em=_utc(item["Created"]),
                atualizado_em=_utc(item["Modified"]),
            )
        )
        rel.contagem["BMs semanais importados"] += 1


def _importar_previstos(session, previstos: list[dict], centros: dict, rel: Relatorio) -> None:
    """Um valor por CC e mês; se a lista repetir o par, vale o último item. Previsto já cadastrado é mantido."""
    ultimos: dict[tuple[str, str], dict] = {}
    for item in previstos:
        codigo, mes = _texto(item["Title"]), _texto(item["Mês de Referência"])
        if codigo is None or mes is None or _vazio(item["Valor Previsto"]):
            continue
        ultimos[(codigo, mes)] = item
    fora = sorted({codigo for codigo, _ in ultimos if codigo not in centros})
    if fora:
        rel.ignorados.append(f"Valor previsto de CCs que não existem na Lista de Apoio: {', '.join(fora)}.")
    for (codigo, mes), item in ultimos.items():
        if codigo not in centros:
            continue
        cc = centros[codigo]
        if session.scalar(
            select(SuperusValorPrevisto.id).where(
                SuperusValorPrevisto.centro_custo_id == cc.id,
                SuperusValorPrevisto.ano == ANO_PREVISTO,
                SuperusValorPrevisto.mes_referencia == mes,
            )
        ):
            rel.contagem["Valores previstos já existentes (mantidos)"] += 1
            continue
        session.add(SuperusValorPrevisto(
            centro_custo_id=cc.id, ano=ANO_PREVISTO, mes_referencia=mes, valor=_dinheiro(item["Valor Previsto"])
        ))
        rel.contagem["Valores previstos importados"] += 1


def _ligar_previstos_aos_bms(session, rel: Relatorio) -> None:
    """Grava nos BMs mensais importados o previsto do CC no mês (para comparar previsto x medido no histórico).
    Não cria justificativa: o SIM antigo não pedia."""
    bms = session.scalars(
        select(SuperusBMMensal).where(SuperusBMMensal.id_legado.is_not(None), SuperusBMMensal.valor_previsto.is_(None))
    ).all()
    previstos = {
        (p.centro_custo_id, p.ano, p.mes_referencia): p.valor for p in session.scalars(select(SuperusValorPrevisto))
    }
    for bm in bms:
        valor = previstos.get((bm.centro_custo_id, bm.ano, bm.mes_referencia))
        if valor is not None:
            # UPDATE direto mantém a data de alteração vinda do SharePoint (o ORM a trocaria por agora).
            session.execute(
                update(SuperusBMMensal)
                .where(SuperusBMMensal.id == bm.id)
                .values(valor_previsto=valor, atualizado_em=SuperusBMMensal.atualizado_em)
            )
            rel.contagem["BMs mensais históricos ligados ao previsto do mês"] += 1


# ------------------------------------------------------------------ entrada ----


def importar(pasta: Path, aplicar: bool = False) -> Relatorio:
    """Importa tudo numa única transação; na simulação, desfaz no final."""
    apoio, bms = _ler(pasta, "Lista de Apoio"), _ler(pasta, "BMs")
    semanais, hist = _ler(pasta, "BM Semanal"), _ler(pasta, "Historico BMs")
    previstos = _ler(pasta, "Valor Previsto")
    rel = Relatorio()
    with session_scope() as session:
        centros = _importar_centros(session, apoio, rel)
        _importar_mensais(session, bms, hist, centros, rel)
        _importar_semanais(session, semanais, centros, rel)
        _importar_previstos(session, previstos, centros, rel)
        session.flush()
        _ligar_previstos_aos_bms(session, rel)
        session.flush()
        if not aplicar:
            session.rollback()
    return rel


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Importa o histórico do SIM antigo (exportações das listas SharePoint).")
    parser.add_argument("pasta", type=Path, help="Pasta com os arquivos 'Base <lista> Lists.xlsx'.")
    parser.add_argument("--aplicar", action="store_true", help="Grava no banco (sem isso, só simula).")
    args = parser.parse_args(argv)
    inicializar()
    importar(args.pasta, args.aplicar).imprimir(args.aplicar)


if __name__ == "__main__":
    main()
