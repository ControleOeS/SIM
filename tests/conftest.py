"""Cada teste usa um banco SQLite em arquivo próprio (pasta temporária do pytest),
criado pelas migrações do Alembic — o mesmo caminho usado pela aplicação."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sim.auth import PERFIL_CONTROLE, Principal, usando_principal  # noqa: E402
from sim import database  # noqa: E402
from sim.bootstrap import migrar  # noqa: E402
from sim.config import load_settings  # noqa: E402
from sim.services import common  # noqa: E402
from sim.storage import ArquivoNovo  # noqa: E402


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    data = tmp_path / "data"
    url = f"sqlite:///{(data / 'teste.db').as_posix()}"
    monkeypatch.setenv("SIM_DATA_DIR", str(data))
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("SIM_ANEXOS_DIR", str(data / "anexos"))
    monkeypatch.setenv("SIM_LOGS_DIR", str(data / "logs"))
    common._storage_para.cache_clear()
    # O ano do BM mensal SUPERUS vem da data de hoje; fixada para os testes não mudarem com o calendário.
    from sim.services import superus

    monkeypatch.setattr(superus, "_hoje", lambda: date(2026, 10, 27))
    settings = load_settings()
    data.mkdir(parents=True, exist_ok=True)
    migrar(url)
    database.init_engine(settings)
    principal = Principal(1, "teste@empresa.test", "Teste", PERFIL_CONTROLE, 1, ())
    try:
        with usando_principal(principal):
            yield settings
    finally:
        database.dispose_engine()
        common._storage_para.cache_clear()


def arquivo(nome: str = "bm.xlsx", conteudo: bytes = b"conteudo de teste") -> ArquivoNovo:
    return ArquivoNovo(nome=nome, conteudo=conteudo)


@pytest.fixture
def novo_arquivo():
    return arquivo
