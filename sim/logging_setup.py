"""Registro de erros técnicos em arquivo (data/logs/sim.log)."""
from __future__ import annotations

import logging
import re
import uuid
from logging.handlers import RotatingFileHandler

from sim.config import Settings, load_settings

LOGGER_NAME = "sim"
_MARCA_HANDLER = "_sim_handler_arquivo"

# Remove senhas de URLs de conexão antes de gravar no log.
_SENHA_URL = re.compile(r"(://[^:/@\s]+:)[^@\s]+@")


class _FormatoSemSegredos(logging.Formatter):
    """Aplica a máscara ao texto final, incluindo tracebacks de exceções."""

    def format(self, record: logging.LogRecord) -> str:
        return _SENHA_URL.sub(r"\1***@", super().format(record))


def configurar_logs(settings: Settings | None = None) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    # Idempotente mesmo se este módulo for recarregado (o logger vive no módulo logging).
    if any(getattr(h, _MARCA_HANDLER, False) for h in logger.handlers):
        return logger
    settings = settings or load_settings()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        settings.logs_dir / "sim.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(_FormatoSemSegredos("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    setattr(handler, _MARCA_HANDLER, True)
    logger.addHandler(handler)
    if settings.log_console:  # hospedagem: o painel de logs lê a saída padrão; o arquivo é efêmero
        console = logging.StreamHandler()
        console.setFormatter(handler.formatter)
        logger.addHandler(console)
    logger.setLevel(logging.INFO)
    return logger


def get_logger(nome: str = "") -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{nome}" if nome else LOGGER_NAME)


def nova_referencia() -> str:
    """Código curto mostrado ao usuário para localizar o erro no log."""
    return uuid.uuid4().hex[:8].upper()
