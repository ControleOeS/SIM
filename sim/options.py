"""Opções das colunas de escolha, centralizadas em config/opcoes.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sim.config import BASE_DIR

OPCOES_PATH = BASE_DIR / "config" / "opcoes.json"

# Valores que aparecem nas fórmulas originais e sustentam regras de negócio.
STATUS_APROVADO_CLIENTE = "BM Aprovado pelo Cliente"
STATUS_EM_ANALISE_CLIENTE = "BM em Análise do Cliente"
STATUS_FATURADO_TOTAL = "Faturado Total"


@dataclass(frozen=True)
class Opcoes:
    chave: str
    valores: tuple[str, ...]
    situacao: str  # "confirmado" | "provisorio"
    origem: str

    @property
    def provisorio(self) -> bool:
        return self.situacao != "confirmado"

    def com_valor_atual(self, atual: str | None) -> list[str]:
        """Lista para um campo de seleção, preservando um valor gravado fora da lista."""
        valores = list(self.valores)
        if atual and atual not in valores:
            valores.insert(0, atual)
        return valores


@lru_cache(maxsize=1)
def _carregar(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def opcoes(chave: str, path: Path = OPCOES_PATH) -> Opcoes:
    dados = _carregar(str(path))
    if chave not in dados:
        raise KeyError(f"Opções não configuradas: {chave}")
    item = dados[chave]
    return Opcoes(
        chave=chave,
        valores=tuple(item["valores"]),
        situacao=item.get("situacao", "provisorio"),
        origem=item.get("origem", ""),
    )


def todas(path: Path = OPCOES_PATH) -> list[Opcoes]:
    return [opcoes(k, path) for k in _carregar(str(path)) if not k.startswith("_")]
