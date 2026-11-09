"""Inicialização: logs, migrações do esquema e engine."""
from __future__ import annotations

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from sim.config import BASE_DIR, Settings, load_settings
from sim.database import get_engine, init_engine
from sim.logging_setup import configurar_logs


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    cfg.attributes["database_url"] = database_url
    cfg.attributes["configure_logger"] = False
    return cfg


def migrar(database_url: str) -> None:
    command.upgrade(alembic_config(database_url), "head")


def versao_atual() -> str | None:
    with get_engine().connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def versao_esperada(database_url: str) -> str | None:
    return ScriptDirectory.from_config(alembic_config(database_url)).get_current_head()


class EsquemaDesatualizado(RuntimeError):
    pass


def inicializar(settings: Settings | None = None) -> Settings:
    """Prepara o banco. Com SIM_AUTO_MIGRATE=false (recomendado em produção),
    apenas confere se o esquema está na versão esperada."""
    settings = settings or load_settings()
    configurar_logs(settings)
    settings.anexos_dir.mkdir(parents=True, exist_ok=True)
    if settings.auto_migrate:
        if settings.is_sqlite:
            settings.data_dir.mkdir(parents=True, exist_ok=True)
        migrar(settings.database_url)
    init_engine(settings)
    esperado = versao_esperada(settings.database_url)
    atual = versao_atual()
    if atual != esperado:
        raise EsquemaDesatualizado(
            f"O banco está na versão {atual or 'vazia'} e o SIM espera {esperado}. "
            "Execute 'alembic upgrade head' (veja o README)."
        )
    return settings
