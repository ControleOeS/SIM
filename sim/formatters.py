"""Formatação e leitura de valores no padrão brasileiro.

Equivalentes às fórmulas originais:
  Text(Value(x), "#,##0.00", "pt-BR")       -> formatar_moeda
  Text(ThisItem.Criado, "dd/mm/yyyy hh:mm") -> formatar_data_hora
  Value(DataCardValueN.Text)                -> ler_decimal
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

try:
    FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")
except Exception:  # pragma: no cover - Windows sem tzdata
    FUSO_LOCAL = None

_MILHAR = re.compile(r"^\d{1,3}(\.\d{3})+$")


class ValorInvalido(ValueError):
    pass


def ler_decimal(texto: object) -> Decimal | None:
    """Converte texto digitado em Decimal.

    Aceita "1.234,56", "1234,56", "1234.56", "-10", "1.234.567" e "R$ 1.234,56".
    Um único ponto seguido de exatamente 3 dígitos ("1.500") é lido como milhar,
    como um usuário brasileiro espera. Texto vazio -> None. Inválido -> ValorInvalido.
    """
    if texto is None:
        return None
    if isinstance(texto, Decimal):
        return texto
    if isinstance(texto, (int, float)):
        return Decimal(str(texto))
    s = str(texto).strip().replace("R$", "").replace(" ", "").replace(" ", "")
    if s == "":
        return None
    negativo = s.startswith("-")
    if negativo:
        s = s[1:]
    if not re.fullmatch(r"[\d.,]+", s):
        raise ValorInvalido(texto)
    if "," in s:
        if s.count(",") > 1:
            raise ValorInvalido(texto)
        inteiro, dec = s.split(",")
        if inteiro == "" and dec == "":
            raise ValorInvalido(texto)
        if "." in inteiro and not _MILHAR.fullmatch(inteiro):
            raise ValorInvalido(texto)
        if not dec.isdigit() and dec != "":
            raise ValorInvalido(texto)
        s = f"{inteiro.replace('.', '')}.{dec or '0'}"
    elif s.count(".") > 1 or _MILHAR.fullmatch(s):
        if not _MILHAR.fullmatch(s):
            raise ValorInvalido(texto)
        s = s.replace(".", "")
    if s in {"", "."} or not re.fullmatch(r"\d*\.?\d+|\d+\.?", s):
        raise ValorInvalido(texto)
    try:
        valor = Decimal(s)
    except InvalidOperation as exc:  # pragma: no cover - coberto pelo regex
        raise ValorInvalido(texto) from exc
    return -valor if negativo else valor


def _agrupar(inteiro: str) -> str:
    partes = []
    while len(inteiro) > 3:
        partes.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    partes.insert(0, inteiro)
    return ".".join(partes)


def formatar_moeda(valor: object, prefixo: str = "") -> str:
    """#.##0,00 (pt-BR). Vazio -> ''."""
    if valor is None or valor == "":
        return ""
    try:
        d = Decimal(str(valor)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return ""
    sinal = "-" if d < 0 else ""
    inteiro, dec = f"{abs(d):.2f}".split(".")
    return f"{sinal}{prefixo}{_agrupar(inteiro)},{dec}"


def formatar_numero(valor: object) -> str:
    """Número sem casas fixas: 15 -> '15', 1234,5 -> '1.234,5'. Vazio -> ''."""
    if valor is None or valor == "":
        return ""
    try:
        d = Decimal(str(valor))
    except InvalidOperation:
        return ""
    sinal = "-" if d < 0 else ""
    texto = f"{abs(d):f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    inteiro, _, dec = texto.partition(".")
    return f"{sinal}{_agrupar(inteiro)}" + (f",{dec}" if dec else "")


def para_local(dt: datetime) -> datetime:
    """As datas são gravadas em UTC (sem fuso); exibe no horário de Brasília."""
    if FUSO_LOCAL is None:
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(FUSO_LOCAL)


def formatar_data_hora(valor: datetime | None) -> str:
    if not valor:
        return ""
    return para_local(valor).strftime("%d/%m/%Y %H:%M")


def formatar_data(valor: date | datetime | None) -> str:
    if not valor:
        return ""
    if isinstance(valor, datetime):
        valor = para_local(valor)
    return valor.strftime("%d/%m/%Y")


def normalizar_chave(texto: str) -> str:
    """Chave de comparação para duplicidade: sem espaços extras, sem caixa."""
    return " ".join(str(texto or "").split()).casefold()
