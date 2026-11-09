"""Autenticação local e contexto de autorização por centro de custo."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterator

from sqlalchemy import select

from sim.config import load_settings
from sim.database import session_scope
from sim.errors import AuthorizationError, ValidationError
from sim.models import (
    AcessoCentroCusto,
    AsapCentroCusto,
    DominioPermitido,
    Empresa,
    SuperusCentroCusto,
    Usuario,
    utcnow,
)

# Perfis (decisão do responsável em 2026-10-27; ver docs, seção "Perfis e permissões").
PERFIL_USUARIO = "usuario"  # Usuário de obras: só os centros de custo liberados, sem área administrativa
PERFIL_PLANEJADOR = "planejador"  # todas as obras (atividades de obra), sem área administrativa
PERFIL_FATURAMENTO = "faturamento"  # só a área administrativa, todas as obras das duas coligadas
PERFIL_CONTROLE = "controle"  # aprova acessos, libera centros, todas as obras e área administrativa
PERFIL_CONTROLE_GERAL = "controle_geral"  # controle total do aplicativo
PERFIS_VALIDOS = (PERFIL_USUARIO, PERFIL_PLANEJADOR, PERFIL_FATURAMENTO, PERFIL_CONTROLE, PERFIL_CONTROLE_GERAL)

PERFIS_CONTROLE = (PERFIL_CONTROLE, PERFIL_CONTROLE_GERAL)  # controle de acesso, cadastro de CC, encerramento
PERFIS_TODAS_OBRAS = (PERFIL_PLANEJADOR, *PERFIS_CONTROLE)
PERFIS_AREA_OBRAS = (PERFIL_USUARIO, *PERFIS_TODAS_OBRAS)
PERFIS_AREA_ADM = (PERFIL_FATURAMENTO, *PERFIS_CONTROLE)

_PBKDF2_ITERATIONS = 600_000
_MAX_TENTATIVAS = 5
_TEMPO_BLOQUEIO = timedelta(minutes=15)
_MIN_SENHA = 8


@dataclass(frozen=True)
class Principal:
    id: int
    email: str
    nome: str
    perfil: str
    versao_sessao: int
    escopos: tuple[tuple[str, int], ...]

    @property
    def area_obras(self) -> bool:
        """Módulos de obra (BMs, encerramento): todos menos o Faturamento."""
        return self.perfil in PERFIS_AREA_OBRAS

    @property
    def area_adm(self) -> bool:
        """Área administrativa (faturamento, planejamento, atualizar dados): Faturamento e Controles."""
        return self.perfil in PERFIS_AREA_ADM

    @property
    def ve_todas_obras(self) -> bool:
        """Escopo global nos módulos de obra (Planejador e Controles)."""
        return self.perfil in PERFIS_TODAS_OBRAS

    @property
    def controlador(self) -> bool:
        """Cadastro de centro de custo e decisões de encerramento."""
        return self.perfil in PERFIS_CONTROLE

    @property
    def administrador_acessos(self) -> bool:
        """Controle de acesso: aprovar pedidos, criar contas, liberar centros, desativar contas."""
        return self.perfil in PERFIS_CONTROLE

    @property
    def controle_geral(self) -> bool:
        """Controle total: domínios, senhas e os perfis Controle/Controle Geral."""
        return self.perfil == PERFIL_CONTROLE_GERAL


_principal_atual: ContextVar[Principal | None] = ContextVar("sim_principal", default=None)


@contextmanager
def usando_principal(principal: Principal) -> Iterator[None]:
    token = _principal_atual.set(principal)
    try:
        yield
    finally:
        _principal_atual.reset(token)


def principal_atual() -> Principal:
    principal = _principal_atual.get()
    if principal is None:
        raise AuthorizationError("Entre no SIM para continuar.")
    return principal


def normalizar_email(email: str) -> str:
    texto = (email or "").strip()
    if texto.count("@") != 1 or len(texto) > 320:
        raise ValidationError({"email": "Informe um e-mail válido."})
    local, dominio = texto.rsplit("@", 1)
    if not local or len(local) > 64 or not dominio or any(c.isspace() for c in local):
        raise ValidationError({"email": "Informe um e-mail válido."})
    try:
        dominio_ascii = dominio.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValidationError({"email": "Informe um e-mail válido."}) from exc
    if len(dominio_ascii) > 253 or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+",
        dominio_ascii,
    ):
        raise ValidationError({"email": "Informe um e-mail válido."})
    return f"{local.casefold()}@{dominio_ascii}"


def normalizar_dominio(dominio: str) -> str:
    texto = (dominio or "").strip().lstrip("@").rstrip(".")
    if not texto or "@" in texto or "/" in texto or "\\" in texto:
        raise ValidationError({"dominio": "Informe somente o domínio, por exemplo empresa.com.br."})
    try:
        resultado = texto.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise ValidationError({"dominio": "Informe um domínio válido."}) from exc
    if len(resultado) > 253 or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+",
        resultado,
    ):
        raise ValidationError({"dominio": "Informe um domínio válido."})
    return resultado


def hash_senha(senha: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        algoritmo, iteracoes, salt_hex, digest_hex = senha_hash.split("$", 3)
        if algoritmo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", senha.encode("utf-8"), bytes.fromhex(salt_hex), int(iteracoes)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def validar_senha(senha: str, confirmacao: str | None = None) -> None:
    erros: dict[str, str] = {}
    if len(senha) < _MIN_SENHA:
        erros["senha"] = f"Use pelo menos {_MIN_SENHA} caracteres."
    elif len(senha) > 256:
        erros["senha"] = "A senha deve ter no máximo 256 caracteres."
    if confirmacao is not None and not hmac.compare_digest(senha, confirmacao):
        erros["confirmacao"] = "As senhas não conferem."
    if erros:
        raise ValidationError(erros)


def _dominio_ativo(session, email_normalizado: str) -> bool:
    dominio = email_normalizado.rsplit("@", 1)[1]
    return (
        session.scalar(
            select(DominioPermitido.id).where(
                DominioPermitido.dominio == dominio,
                DominioPermitido.ativo.is_(True),
            )
        )
        is not None
    )


def autenticar(email: str, senha: str) -> tuple[int, int] | None:
    """Retorna (usuário, versão da sessão); credenciais inválidas têm resposta uniforme."""
    try:
        email_normalizado = normalizar_email(email)
    except ValidationError:
        email_normalizado = ""

    with session_scope() as session:
        usuario = session.scalar(
            select(Usuario).where(Usuario.email_normalizado == email_normalizado)
        ) if email_normalizado else None
        # Mantém trabalho criptográfico também para e-mails inexistentes.
        hash_referencia = usuario.senha_hash if usuario else (
            "pbkdf2_sha256$600000$" + ("00" * 16) + "$" + ("00" * 32)
        )
        senha_correta = verificar_senha(senha, hash_referencia)
        agora = utcnow()

        if usuario is None or not usuario.ativo or not _dominio_ativo(session, email_normalizado):
            return None
        if usuario.bloqueado_ate and usuario.bloqueado_ate > agora:
            return None
        if not senha_correta:
            usuario.tentativas_login += 1
            if usuario.tentativas_login >= _MAX_TENTATIVAS:
                usuario.tentativas_login = 0
                usuario.bloqueado_ate = agora + _TEMPO_BLOQUEIO
            return None

        usuario.tentativas_login = 0
        usuario.bloqueado_ate = None
        usuario.ultimo_login_em = agora
        return usuario.id, usuario.versao_sessao


def carregar_principal(usuario_id: int, versao_sessao: int) -> Principal | None:
    with session_scope() as session:
        usuario = session.get(Usuario, usuario_id)
        if (
            usuario is None
            or not usuario.ativo
            or usuario.versao_sessao != versao_sessao
            or not _dominio_ativo(session, usuario.email_normalizado)
        ):
            return None

        acessos = session.scalars(
            select(AcessoCentroCusto).where(AcessoCentroCusto.usuario_id == usuario.id)
        ).all()
        empresas = {e.id: e.codigo for e in session.scalars(select(Empresa))}
        escopos: list[tuple[str, int]] = []
        for acesso in acessos:
            if acesso.asap_centro_custo_id is not None:
                centro = session.get(AsapCentroCusto, acesso.asap_centro_custo_id)
                empresa_codigo = "ASAP"
            else:
                centro = session.get(SuperusCentroCusto, acesso.superus_centro_custo_id)
                empresa_codigo = "SUPERUS"
            if centro is not None and empresas.get(acesso.empresa_id) == empresa_codigo and centro.empresa_id == acesso.empresa_id:
                escopos.append((empresa_codigo, centro.id))
        return Principal(
            usuario.id,
            usuario.email,
            usuario.nome,
            usuario.perfil,
            usuario.versao_sessao,
            tuple(sorted(set(escopos))),
        )


def existe_administrador_inicializado() -> bool:
    with session_scope() as session:
        return (
            session.scalar(
                select(Usuario.id).where(
                    Usuario.ativo.is_(True),
                    Usuario.perfil.in_(PERFIS_CONTROLE),
                ).limit(1)
            )
            is not None
        )


def existe_algum_usuario() -> bool:
    with session_scope() as session:
        return session.scalar(select(Usuario.id).limit(1)) is not None


def configuracao_exige_codigo() -> bool:
    return bool(load_settings().codigo_configuracao)


def criar_primeiro_administrador(
    email: str, nome: str, senha: str, confirmacao: str, codigo: str = ""
) -> tuple[int, int]:
    """Cria o Controle Geral inicial e autoriza o domínio dele; só funciona com o banco sem usuários.

    Se SIM_CODIGO_CONFIGURACAO estiver definido (obrigatório em endereço público), exige esse código:
    sem ele, a primeira pessoa a abrir o endereço viraria administradora.
    """
    erros: dict[str, str] = {}
    esperado = load_settings().codigo_configuracao
    if esperado and not hmac.compare_digest((codigo or "").strip().encode(), esperado.encode()):
        erros["codigo"] = "Código de configuração incorreto."
    nome = nome.strip()
    if not nome or len(nome) > 255:
        erros["nome"] = "Informe um nome de 1 a 255 caracteres."
    try:
        email_normalizado = normalizar_email(email)
        dominio = normalizar_dominio(email_normalizado.rsplit("@", 1)[1])
    except ValidationError as exc:
        erros.update(exc.errors)
    try:
        validar_senha(senha, confirmacao)
    except ValidationError as exc:
        erros.update(exc.errors)
    if erros:
        raise ValidationError(erros)

    with session_scope() as session:
        if session.scalar(select(Usuario.id).limit(1)) is not None:
            raise AuthorizationError("O primeiro administrador já foi criado. Entre com uma conta existente.")
        dominio_existente = session.scalar(
            select(DominioPermitido).where(DominioPermitido.dominio == dominio)
        )
        if dominio_existente is None:
            session.add(DominioPermitido(dominio=dominio, ativo=True))
        else:
            dominio_existente.ativo = True
        usuario = Usuario(
            email=email.strip(),
            email_normalizado=email_normalizado,
            nome=nome,
            senha_hash=hash_senha(senha),
            perfil=PERFIL_CONTROLE_GERAL,
            ativo=True,
            deve_trocar_senha=False,
        )
        session.add(usuario)
        session.flush()
        return usuario.id, usuario.versao_sessao


def deve_trocar_senha(usuario_id: int) -> bool:
    with session_scope() as session:
        usuario = session.get(Usuario, usuario_id)
        return bool(usuario and usuario.ativo and usuario.deve_trocar_senha)


MSG_TROCA_SO_ADMIN = (
    "A troca de senha pelo sistema é exclusiva dos perfis Controle e Controle Geral. "
    "Solicite a troca por e-mail a um controlador do SIM."
)


def trocar_senha(usuario_id: int, senha_atual: str, senha_nova: str, confirmacao: str) -> int:
    validar_senha(senha_nova, confirmacao)
    principal = principal_atual()
    if principal.id != usuario_id:
        raise AuthorizationError("Você só pode alterar sua própria senha.")

    with session_scope() as session:
        usuario = session.get(Usuario, usuario_id)
        if usuario is None or not usuario.ativo:
            raise AuthorizationError("A conta não está ativa.")
        # Troca voluntária só para administradores (decisão de 2026-10-27); os demais trocam a senha
        # temporária no primeiro acesso e, depois, pedem a troca por e-mail.
        if not usuario.deve_trocar_senha and usuario.perfil not in PERFIS_CONTROLE:
            raise AuthorizationError(MSG_TROCA_SO_ADMIN)
        if not verificar_senha(senha_atual, usuario.senha_hash):
            raise ValidationError({"senha_atual": "A senha atual está incorreta."})
        if verificar_senha(senha_nova, usuario.senha_hash):
            raise ValidationError({"senha": "Escolha uma senha diferente da atual."})
        usuario.senha_hash = hash_senha(senha_nova)
        usuario.deve_trocar_senha = False
        usuario.versao_sessao += 1
        usuario.tentativas_login = 0
        usuario.bloqueado_ate = None
        return usuario.versao_sessao


def escopos_centros(empresa: str, *, escrita: bool = False) -> set[int] | None:
    """None representa acesso global; conjunto vazio representa nenhum escopo."""
    principal = principal_atual()
    # Faturamento enxerga (e fatura) todas as obras; o bloqueio das telas de obra é exigir_area_obras.
    if principal.ve_todas_obras or principal.area_adm:
        return None
    return {id_cc for nome_empresa, id_cc in principal.escopos if nome_empresa == empresa}


def exigir_centro(empresa: str, centro_custo_id: int, *, escrita: bool = False) -> None:
    escopos = escopos_centros(empresa, escrita=escrita)
    if escopos is not None and centro_custo_id not in escopos:
        acao = "alterar" if escrita else "acessar"
        raise AuthorizationError(f"Você não tem permissão para {acao} este centro de custo.")


def exigir_controlador() -> None:
    if not principal_atual().controlador:
        raise AuthorizationError("Somente os perfis Controle e Controle Geral podem executar esta operação.")


def exigir_administrador_acessos() -> None:
    if not principal_atual().administrador_acessos:
        raise AuthorizationError("Somente os perfis Controle e Controle Geral podem abrir o controle de acesso.")


def exigir_controle_geral() -> None:
    if not principal_atual().controle_geral:
        raise AuthorizationError("Somente o Controle Geral pode executar esta operação.")


def exigir_area_obras() -> None:
    if not principal_atual().area_obras:
        raise AuthorizationError("Seu perfil não tem acesso às telas de obra.")


def exigir_area_adm() -> None:
    if not principal_atual().area_adm:
        raise AuthorizationError("Seu perfil não tem acesso à área administrativa.")
