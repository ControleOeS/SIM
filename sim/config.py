"""Configuração da aplicação, lida de variáveis de ambiente (ou do arquivo .env).

Nenhuma credencial fica no código. Para trocar o banco, altere apenas DATABASE_URL
(veja README, seção "Migração para o banco corporativo").
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=False)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    p = Path(raw) if raw else default
    return p if p.is_absolute() else (BASE_DIR / p)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    anexos_dir: Path
    logs_dir: Path
    auto_migrate: bool
    sql_echo: bool
    max_anexo_mb: int
    # Onde fica o conteúdo dos anexos: "disco" (SIM_ANEXOS_DIR) ou "banco" (tabela anexos_conteudo).
    anexos_backend: str = "disco"
    # Logs também na saída padrão (painel de logs da hospedagem).
    log_console: bool = False
    # Código exigido na tela de configuração inicial (primeiro Controle Geral), se definido.
    codigo_configuracao: str = field(default="", repr=False)
    # Envio de e-mail (redefinição de senha). Modos: "desativado", "arquivo" (grava em
    # <data>/emails, só para desenvolvimento) ou "smtp".
    email_modo: str = "desativado"
    email_remetente: str = ""
    smtp_host: str = ""
    smtp_porta: int = 587
    smtp_usuario: str = ""
    smtp_senha: str = field(default="", repr=False)
    smtp_starttls: bool = True

    @property
    def emails_dir(self) -> Path:
        return self.data_dir / "emails"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def normalizar_url_banco(url: str) -> str:
    """Provedores (Neon, Supabase, Render) entregam 'postgresql://' ou 'postgres://', que o SQLAlchemy
    associaria ao psycopg2. O SIM usa o psycopg 3."""
    for prefixo in ("postgresql://", "postgres://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg://" + url[len(prefixo):]
    return url


def load_settings() -> Settings:
    data_dir = _path("SIM_DATA_DIR", BASE_DIR / "data")
    default_db = f"sqlite:///{(data_dir / 'sim.db').as_posix()}"
    return Settings(
        data_dir=data_dir,
        database_url=normalizar_url_banco((os.getenv("DATABASE_URL") or "").strip() or default_db),
        anexos_dir=_path("SIM_ANEXOS_DIR", data_dir / "anexos"),
        logs_dir=_path("SIM_LOGS_DIR", data_dir / "logs"),
        auto_migrate=_bool("SIM_AUTO_MIGRATE", True),
        sql_echo=_bool("SIM_SQL_ECHO", False),
        max_anexo_mb=int(os.getenv("SIM_MAX_ANEXO_MB", "50")),
        anexos_backend=(os.getenv("SIM_ANEXOS_BACKEND") or "disco").strip().lower(),
        log_console=_bool("SIM_LOG_CONSOLE", False),
        codigo_configuracao=os.getenv("SIM_CODIGO_CONFIGURACAO", "").strip(),
        email_modo=(os.getenv("SIM_EMAIL_MODO") or "desativado").strip().lower(),
        email_remetente=os.getenv("SIM_EMAIL_REMETENTE", "").strip(),
        smtp_host=os.getenv("SIM_SMTP_HOST", "").strip(),
        smtp_porta=int(os.getenv("SIM_SMTP_PORTA") or "587"),
        smtp_usuario=os.getenv("SIM_SMTP_USUARIO", "").strip(),
        smtp_senha=os.getenv("SIM_SMTP_SENHA", ""),
        smtp_starttls=_bool("SIM_SMTP_STARTTLS", True),
    )
