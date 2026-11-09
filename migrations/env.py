"""Ambiente do Alembic. A URL vem de sim.config (DATABASE_URL ou SQLite local)."""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from sim.config import load_settings
from sim.database import build_engine
from sim.models import Base

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _url() -> str:
    return config.attributes.get("database_url") or load_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    url = _url()
    if url.startswith("sqlite:///"):
        load_settings().data_dir.mkdir(parents=True, exist_ok=True)
    engine = build_engine(url)
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()


def _run(connection) -> None:
    # No SQLite, o modo batch altera uma tabela recriando-a (copia, apaga a original e renomeia).
    # Com foreign_keys=ON, apagar a original dispara ON DELETE CASCADE/RESTRICT nas tabelas
    # filhas: grants e anexos seriam apagados em silêncio, ou a migração falharia com dados.
    # Por isso a verificação fica desligada durante a migração e a integridade é conferida no fim.
    # (O PRAGMA só tem efeito fora de transação.)
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
    try:
        # render_as_batch: permite ALTER TABLE no SQLite; é ignorado nos demais bancos.
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
            if sqlite:
                violacoes = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if violacoes:
                    raise RuntimeError(f"Migração deixou chaves estrangeiras inválidas: {violacoes[:10]}")
    finally:
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
