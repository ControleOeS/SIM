"""Envio de e-mails do SIM (hoje: código de redefinição de senha).

O modo vem de SIM_EMAIL_MODO (ver sim/config.py). Nenhuma credencial fica no código.
"""
from __future__ import annotations

import smtplib
import ssl
import uuid
from datetime import datetime
from email.message import EmailMessage

from sim.config import Settings, load_settings

MODO_DESATIVADO = "desativado"
MODO_ARQUIVO = "arquivo"
MODO_SMTP = "smtp"


class EnvioIndisponivel(RuntimeError):
    """O envio não está configurado ou falhou; a causa vai para o log, não para a tela."""


def envio_configurado(settings: Settings | None = None) -> bool:
    settings = settings or load_settings()
    if settings.email_modo == MODO_ARQUIVO:
        return True
    return settings.email_modo == MODO_SMTP and bool(settings.smtp_host and settings.email_remetente)


def enviar(destinatario: str, assunto: str, corpo: str, settings: Settings | None = None) -> None:
    settings = settings or load_settings()
    if not envio_configurado(settings):
        raise EnvioIndisponivel("Envio de e-mail não configurado.")

    mensagem = EmailMessage()
    mensagem["From"] = settings.email_remetente or "sim@localhost"
    mensagem["To"] = destinatario
    mensagem["Subject"] = assunto
    mensagem.set_content(corpo)

    if settings.email_modo == MODO_ARQUIVO:
        settings.emails_dir.mkdir(parents=True, exist_ok=True)
        nome = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{uuid.uuid4().hex[:8]}.eml"
        (settings.emails_dir / nome).write_bytes(bytes(mensagem))
        return

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_porta, timeout=20) as smtp:
            if settings.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_usuario:
                smtp.login(settings.smtp_usuario, settings.smtp_senha)
            smtp.send_message(mensagem)
    except (OSError, smtplib.SMTPException) as exc:
        raise EnvioIndisponivel(f"Falha no envio SMTP: {type(exc).__name__}") from exc
