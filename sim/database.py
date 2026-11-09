"""Conexão com o banco e criação de sessões (SQLAlchemy).

É o único módulo que conhece detalhes do banco. Os ajustes específicos do SQLite
(chaves estrangeiras, modo WAL e espera por gravações concorrentes) ficam isolados aqui.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from sim.config import Settings, load_settings

# Quanto uma gravação espera outra terminar antes de desistir ("database is locked").
SQLITE_ESPERA_SEGUNDOS = 15

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def build_engine(database_url: str, echo: bool = False) -> Engine:
    kwargs: dict = {"echo": echo, "future": True, "pool_pre_ping": True}
    if database_url.startswith("sqlite"):
        # Streamlit atende cada sessão em threads diferentes.
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": SQLITE_ESPERA_SEGUNDOS}
    else:
        # Bancos gerenciados (ex.: Neon) encerram conexões ociosas; recicla antes disso.
        kwargs["pool_recycle"] = 300
    engine = create_engine(database_url, **kwargs)

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            # WAL: leituras não bloqueiam a gravação nem são bloqueadas por ela. Fica gravado no arquivo
            # do banco (cópias de segurança devem levar também sim.db-wal, ou usar a API de backup).
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")  # recomendado com WAL; não corrompe em queda
            cur.execute(f"PRAGMA busy_timeout={SQLITE_ESPERA_SEGUNDOS * 1000}")
            cur.close()

    return engine


def init_engine(settings: Settings | None = None, database_url: str | None = None) -> Engine:
    """(Re)cria o engine global. Usado na inicialização e nos testes."""
    global _engine, _session_factory
    settings = settings or load_settings()
    url = database_url or settings.database_url
    if url.startswith("sqlite:///"):
        settings.data_dir.mkdir(parents=True, exist_ok=True)
    if _engine is not None:
        _engine.dispose()
    _engine = build_engine(url, echo=settings.sql_echo)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        init_engine()
    assert _engine is not None
    return _engine


def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessão com commit no fim e rollback em qualquer erro."""
    get_engine()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
