"""Redefinição de senha pelo próprio usuário, com código enviado ao e-mail da conta.

Fluxo público (sem usuário autenticado):
1. `solicitar_codigo(email)`: se houver conta ativa, gera um código de 6 dígitos e envia por e-mail.
   A resposta é sempre a mesma, para não revelar quais e-mails têm conta.
2. `redefinir_com_codigo(email, codigo, nova, confirmacao)`: confere o código e grava a nova senha.

O código vale por 15 minutos, aceita até 5 tentativas e é guardado só como hash.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import timedelta

from sqlalchemy import delete, func, select

from sim import envio_email
from sim.auth import _dominio_ativo, hash_senha, normalizar_email, validar_senha
from sim.database import session_scope
from sim.errors import ValidationError
from sim.logging_setup import get_logger
from sim.models import AuditoriaAcesso, CodigoRedefinicaoSenha, Usuario, utcnow

VALIDADE = timedelta(minutes=15)
MAX_TENTATIVAS = 5
INTERVALO_MINIMO = timedelta(seconds=60)
MAX_CODIGOS_POR_HORA = 5
_ERRO_CODIGO = "Código inválido ou expirado. Peça um novo código."


def disponivel() -> bool:
    return envio_email.envio_configurado()


def _hash_codigo(codigo: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hmac.new(salt, codigo.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{salt.hex()}${digest}"


def _confere(codigo: str, codigo_hash: str) -> bool:
    try:
        salt_hex, _ = codigo_hash.split("$", 1)
        return hmac.compare_digest(_hash_codigo(codigo, bytes.fromhex(salt_hex)), codigo_hash)
    except ValueError:
        return False


def _usuario_apto(session, email_normalizado: str) -> Usuario | None:
    usuario = session.scalar(select(Usuario).where(Usuario.email_normalizado == email_normalizado))
    if usuario is None or not usuario.ativo or not _dominio_ativo(session, email_normalizado):
        return None
    return usuario


def solicitar_codigo(email: str) -> None:
    try:
        email_normalizado = normalizar_email(email)
    except ValidationError:
        raise ValidationError({"email": "Informe um e-mail válido."}) from None
    if not disponivel():
        return

    agora = utcnow()
    codigo = f"{secrets.randbelow(10**6):06d}"
    with session_scope() as session:
        usuario = _usuario_apto(session, email_normalizado)
        if usuario is None:
            return
        ultimo = session.scalar(
            select(func.max(CodigoRedefinicaoSenha.criado_em)).where(
                CodigoRedefinicaoSenha.usuario_id == usuario.id
            )
        )
        recentes = session.scalar(
            select(func.count(CodigoRedefinicaoSenha.id)).where(
                CodigoRedefinicaoSenha.usuario_id == usuario.id,
                CodigoRedefinicaoSenha.criado_em > agora - timedelta(hours=1),
            )
        )
        if (ultimo and ultimo > agora - INTERVALO_MINIMO) or recentes >= MAX_CODIGOS_POR_HORA:
            return
        # Limpeza: códigos não usados com mais de 1 hora já não contam para nada.
        session.execute(
            delete(CodigoRedefinicaoSenha).where(
                CodigoRedefinicaoSenha.usuario_id == usuario.id,
                CodigoRedefinicaoSenha.usado_em.is_(None),
                CodigoRedefinicaoSenha.criado_em <= agora - timedelta(hours=1),
            )
        )
        for antigo in session.scalars(
            select(CodigoRedefinicaoSenha).where(
                CodigoRedefinicaoSenha.usuario_id == usuario.id,
                CodigoRedefinicaoSenha.usado_em.is_(None),
            )
        ):
            antigo.tentativas = MAX_TENTATIVAS  # um código novo invalida os anteriores

        session.add(
            CodigoRedefinicaoSenha(
                usuario_id=usuario.id,
                codigo_hash=_hash_codigo(codigo),
                expira_em=agora + VALIDADE,
                tentativas=0,
            )
        )
        destinatario, nome = usuario.email, usuario.nome

    try:
        envio_email.enviar(
            destinatario,
            "SIM - código para redefinir sua senha",
            f"Olá, {nome}.\n\n"
            f"Seu código para redefinir a senha do SIM é: {codigo}\n\n"
            f"Ele vale por {int(VALIDADE.total_seconds() // 60)} minutos e só pode ser usado uma vez.\n"
            "Se você não pediu a redefinição, ignore este e-mail; sua senha atual continua valendo.\n\n"
            "O&S Gestão · SIM",
        )
    except envio_email.EnvioIndisponivel:
        get_logger("redefinicao_senha").exception("Falha ao enviar o código de redefinição de senha")


def redefinir_com_codigo(email: str, codigo: str, nova_senha: str, confirmacao: str) -> None:
    validar_senha(nova_senha, confirmacao)
    codigo = (codigo or "").strip()
    try:
        email_normalizado = normalizar_email(email)
    except ValidationError:
        raise ValidationError({"codigo": _ERRO_CODIGO}) from None

    agora = utcnow()
    with session_scope() as session:
        usuario = _usuario_apto(session, email_normalizado)
        registro = None
        if usuario is not None:
            registro = session.scalar(
                select(CodigoRedefinicaoSenha)
                .where(
                    CodigoRedefinicaoSenha.usuario_id == usuario.id,
                    CodigoRedefinicaoSenha.usado_em.is_(None),
                    CodigoRedefinicaoSenha.expira_em > agora,
                    CodigoRedefinicaoSenha.tentativas < MAX_TENTATIVAS,
                )
                .order_by(CodigoRedefinicaoSenha.criado_em.desc(), CodigoRedefinicaoSenha.id.desc())
                .limit(1)
            )
        if registro is None:
            raise ValidationError({"codigo": _ERRO_CODIGO})
        if not (codigo.isdigit() and len(codigo) == 6 and _confere(codigo, registro.codigo_hash)):
            registro.tentativas += 1
            # Sai do bloco normalmente para gravar a tentativa; o erro é levantado depois.
            falhou = True
        else:
            falhou = False
            registro.usado_em = agora
            usuario.senha_hash = hash_senha(nova_senha)
            usuario.deve_trocar_senha = False
            usuario.versao_sessao += 1
            usuario.tentativas_login = 0
            usuario.bloqueado_ate = None
            session.add(
                AuditoriaAcesso(
                    ator_usuario_id=usuario.id,
                    alvo_usuario_id=usuario.id,
                    acao="redefinir_senha_por_email",
                    detalhes=json.dumps({"email": email_normalizado}, ensure_ascii=True),
                )
            )
    if falhou:
        raise ValidationError({"codigo": _ERRO_CODIGO})
