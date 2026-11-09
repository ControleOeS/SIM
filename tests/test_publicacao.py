"""Ajustes para a hospedagem online (Streamlit Community Cloud + PostgreSQL)."""
from __future__ import annotations

import pytest

from sim import auth
from sim.config import normalizar_url_banco
from sim.errors import ValidationError


@pytest.mark.parametrize("entrada, esperado", [
    ("postgresql://u:s@ep-x.neon.tech/sim?sslmode=require", "postgresql+psycopg://u:s@ep-x.neon.tech/sim?sslmode=require"),
    ("postgres://u:s@host/db", "postgresql+psycopg://u:s@host/db"),
    ("postgresql+psycopg://u:s@host/db", "postgresql+psycopg://u:s@host/db"),
    ("sqlite:///data/sim.db", "sqlite:///data/sim.db"),
])
def test_url_do_provedor_usa_psycopg3(entrada, esperado):
    assert normalizar_url_banco(entrada) == esperado


def test_configuracao_inicial_exige_codigo_quando_definido(ambiente, monkeypatch):
    monkeypatch.setenv("SIM_CODIGO_CONFIGURACAO", "codigo-secreto-123")
    assert auth.configuracao_exige_codigo()
    for codigo in ("", "errado"):
        with pytest.raises(ValidationError) as erro:
            auth.criar_primeiro_administrador("dono@empresa.test", "Dono", "senha-boa-1", "senha-boa-1", codigo)
        assert "codigo" in erro.value.errors
    assert not auth.existe_algum_usuario()
    auth.criar_primeiro_administrador("dono@empresa.test", "Dono", "senha-boa-1", "senha-boa-1", "codigo-secreto-123")
    assert auth.existe_administrador_inicializado()


def test_configuracao_inicial_sem_codigo_continua_funcionando(ambiente, monkeypatch):
    monkeypatch.delenv("SIM_CODIGO_CONFIGURACAO", raising=False)
    assert not auth.configuracao_exige_codigo()
    auth.criar_primeiro_administrador("dono@empresa.test", "Dono", "senha-boa-1", "senha-boa-1")
