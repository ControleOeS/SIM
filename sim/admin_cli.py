"""Comandos locais de provisionamento inicial do SIM."""
from __future__ import annotations

import argparse
from getpass import getpass

from sqlalchemy import select

from sim.auth import (
    PERFIS_CONTROLE,
    criar_primeiro_administrador as criar_primeiro_admin,
    existe_algum_usuario,
    hash_senha,
    normalizar_email,
    validar_senha,
)
from sim.bootstrap import inicializar
from sim.database import session_scope
from sim.errors import SimError, ValidationError
from sim.models import Usuario


def _solicitar_senha() -> str:
    while True:
        senha = getpass("Defina uma senha (mínimo 8 caracteres): ")
        confirmacao = getpass("Confirme a senha: ")
        try:
            validar_senha(senha, confirmacao)
            return senha
        except ValidationError as exc:
            print(exc.message)
            for mensagem in exc.errors.values():
                print(f"- {mensagem}")


def criar_primeiro_administrador(email: str, nome: str) -> None:
    inicializar()
    if existe_algum_usuario():
        raise SystemExit("O banco já possui usuários; use o painel de controle de acesso.")

    senha = _solicitar_senha()
    try:
        criar_primeiro_admin(email, nome, senha, senha)
    except ValidationError as exc:
        raise SystemExit("; ".join(exc.errors.values()) or exc.message) from exc
    except SimError as exc:
        raise SystemExit(exc.message) from exc

    email_normalizado = normalizar_email(email)
    print(f"Administrador inicial criado para {email_normalizado}.")
    print(f"Domínio autorizado: {email_normalizado.rsplit('@', 1)[1]}")
    print("Guarde a senha em um gerenciador seguro. O SIM não poderá recuperá-la.")


def redefinir_senha_administrador(email: str) -> None:
    inicializar()
    email_normalizado = normalizar_email(email)
    with session_scope() as session:
        existe = session.scalar(
            select(Usuario).where(
                Usuario.email_normalizado == email_normalizado,
                Usuario.perfil.in_(PERFIS_CONTROLE),
                Usuario.ativo.is_(True),
            )
        )
        if existe is None:
            raise SystemExit("Administrador ativo não encontrado.")

    senha = _solicitar_senha()
    with session_scope() as session:
        usuario = session.scalar(
            select(Usuario).where(
                Usuario.email_normalizado == email_normalizado,
                Usuario.perfil.in_(PERFIS_CONTROLE),
                Usuario.ativo.is_(True),
            )
        )
        if usuario is None:
            raise SystemExit("Administrador foi removido durante a operação.")
        usuario.senha_hash = hash_senha(senha)
        usuario.deve_trocar_senha = True
        usuario.versao_sessao += 1
        usuario.tentativas_login = 0
        usuario.bloqueado_ate = None
    print(f"Senha redefinida para {email_normalizado}. Será obrigatório trocá-la no próximo acesso.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provisionamento local e seguro do SIM.")
    subparsers = parser.add_subparsers(dest="comando", required=True)
    primeiro = subparsers.add_parser(
        "criar-primeiro-admin",
        help="Cria o único administrador inicial; só funciona quando ainda não há usuários.",
    )
    primeiro.add_argument("email")
    primeiro.add_argument("nome")
    redefinir = subparsers.add_parser(
        "redefinir-senha-admin",
        help="Redefine localmente a senha de um administrador ativo, exigindo troca no próximo acesso.",
    )
    redefinir.add_argument("email")
    args = parser.parse_args()

    if args.comando == "criar-primeiro-admin":
        criar_primeiro_administrador(args.email, args.nome)
    elif args.comando == "redefinir-senha-admin":
        redefinir_senha_administrador(args.email)


if __name__ == "__main__":
    main()
