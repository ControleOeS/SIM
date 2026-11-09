"""Operações administrativas para contas, domínios e escopos."""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from sim.auth import (
    PERFIL_CONTROLE,
    PERFIL_CONTROLE_GERAL,
    PERFIL_FATURAMENTO,
    PERFIL_PLANEJADOR,
    PERFIL_USUARIO,
    PERFIS_CONTROLE,
    PERFIS_VALIDOS,
    exigir_administrador_acessos,
    exigir_controle_geral,
    hash_senha,
    normalizar_dominio,
    normalizar_email,
    principal_atual,
    validar_senha,
)
from sim.database import session_scope
from sim.errors import AuthorizationError, NotFoundError, ValidationError
from sim.models import (
    AcessoCentroCusto,
    AsapCentroCusto,
    AuditoriaAcesso,
    DominioPermitido,
    Empresa,
    SolicitacaoAcesso,
    SuperusCentroCusto,
    Usuario,
    utcnow,
)

PERFIS = PERFIS_VALIDOS
ROTULOS_PERFIL = {
    PERFIL_USUARIO: "Usuário de obras (só os centros de custo liberados)",
    PERFIL_PLANEJADOR: "Planejador (todas as obras, sem área administrativa)",
    PERFIL_FATURAMENTO: "Faturamento (só a área administrativa, ASAP e SUPERUS)",
    PERFIL_CONTROLE: "Controle (aprova acessos e acessa todas as obras)",
    PERFIL_CONTROLE_GERAL: "Controle Geral (controle total do aplicativo)",
}
MSG_SO_CONTROLE_GERAL = (
    "Somente o Controle Geral pode conceder, alterar ou desativar contas com perfil Controle ou Controle Geral."
)
STATUS_PENDENTE = "pendente"
STATUS_APROVADA = "aprovada"
STATUS_RECUSADA = "recusada"
# Teto de pedidos em aberto: o formulário é público e não deve permitir encher o banco.
_MAX_SOLICITACOES_PENDENTES = 500


@dataclass(frozen=True)
class AcessoResumo:
    id: int
    empresa: str
    centro_custo_id: int
    titulo: str


def _registrar(session, acao: str, *, alvo: int | None = None, **detalhes) -> None:
    session.add(
        AuditoriaAcesso(
            ator_usuario_id=principal_atual().id,
            alvo_usuario_id=alvo,
            acao=acao,
            detalhes=json.dumps(detalhes, ensure_ascii=True, sort_keys=True),
        )
    )


def _exigir_pode_gerir_perfil(*perfis: str) -> None:
    """O perfil Controle administra contas, mas não concede nem mexe em contas de nível Controle."""
    if not principal_atual().controle_geral and any(p in PERFIS_CONTROLE for p in perfis):
        raise AuthorizationError(MSG_SO_CONTROLE_GERAL)


def _manter_um_controle_geral(session, usuario: Usuario, campo: str) -> None:
    """Chamar antes de desativar ou rebaixar `usuario`: o sistema não pode ficar sem Controle Geral ativo."""
    if not (usuario.ativo and usuario.perfil == PERFIL_CONTROLE_GERAL):
        return
    restantes = session.scalar(
        select(Usuario.id).where(
            Usuario.ativo.is_(True),
            Usuario.perfil == PERFIL_CONTROLE_GERAL,
            Usuario.id != usuario.id,
        ).limit(1)
    )
    if restantes is None:
        raise ValidationError({campo: "Mantenha pelo menos uma conta Controle Geral ativa."})


def _usuario_ativo(session, usuario_id: int) -> Usuario:
    usuario = session.get(Usuario, usuario_id)
    if usuario is None:
        raise NotFoundError("Usuário não encontrado.")
    return usuario


def listar_dominios() -> list[DominioPermitido]:
    exigir_administrador_acessos()
    with session_scope() as session:
        return list(session.scalars(select(DominioPermitido).order_by(DominioPermitido.dominio)))


def adicionar_dominio(dominio: str) -> None:
    exigir_controle_geral()
    normalizado = normalizar_dominio(dominio)
    with session_scope() as session:
        existente = session.scalar(select(DominioPermitido).where(DominioPermitido.dominio == normalizado))
        if existente:
            if existente.ativo:
                raise ValidationError({"dominio": "Este domínio já está autorizado."})
            existente.ativo = True
        else:
            session.add(DominioPermitido(dominio=normalizado, ativo=True))
        _registrar(session, "adicionar_dominio", dominio=normalizado)


def desativar_dominio(dominio_id: int) -> None:
    exigir_controle_geral()
    with session_scope() as session:
        dominio = session.get(DominioPermitido, dominio_id)
        if dominio is None:
            raise NotFoundError("Domínio não encontrado.")
        administradores = session.scalars(
            select(Usuario).where(
                Usuario.ativo.is_(True),
                Usuario.perfil.in_(PERFIS_CONTROLE),
            )
        ).all()
        if any(u.email_normalizado.rsplit("@", 1)[1] == dominio.dominio for u in administradores):
            raise ValidationError(
                {"dominio": "Não é possível desativar o domínio usado por uma conta Controle ativa."}
            )
        dominio.ativo = False
        _registrar(session, "desativar_dominio", dominio=dominio.dominio)


def listar_usuarios() -> list[Usuario]:
    exigir_administrador_acessos()
    with session_scope() as session:
        return list(session.scalars(select(Usuario).order_by(Usuario.email_normalizado)))


def criar_usuario(
    email: str, nome: str, perfil: str = PERFIL_USUARIO, centros: list[tuple[str, int]] | None = None
) -> tuple[int, str]:
    """Cria a conta com senha temporária. Usuário de obra já nasce com os centros de custo liberados
    (pelo menos um); para os demais perfis, `centros` é ignorado (eles enxergam tudo ou administram contas).
    """
    exigir_administrador_acessos()
    email_normalizado = normalizar_email(email)
    nome_normalizado = (nome or "").strip()
    if not nome_normalizado or len(nome_normalizado) > 255:
        raise ValidationError({"nome": "Informe um nome (até 255 caracteres)."})
    if perfil not in PERFIS:
        raise ValidationError({"perfil": "Perfil inválido."})
    _exigir_pode_gerir_perfil(perfil)
    centros = list(dict.fromkeys(centros or [])) if perfil == PERFIL_USUARIO else []
    if perfil == PERFIL_USUARIO and not centros:
        raise ValidationError(
            {"centro_custo": "Escolha a coligada e pelo menos um centro de custo para o usuário de obra."}
        )

    dominio_email = email_normalizado.rsplit("@", 1)[1]
    senha_temporaria = secrets.token_urlsafe(18)
    with session_scope() as session:
        if not session.scalar(
            select(DominioPermitido.id).where(
                DominioPermitido.dominio == dominio_email,
                DominioPermitido.ativo.is_(True),
            )
        ):
            raise ValidationError({"email": "O domínio deste e-mail não está autorizado."})
        if session.scalar(select(Usuario.id).where(Usuario.email_normalizado == email_normalizado)):
            raise ValidationError({"email": "Já existe uma conta para este e-mail."})
        usuario = Usuario(
            email=email.strip(),
            email_normalizado=email_normalizado,
            nome=nome_normalizado,
            senha_hash=hash_senha(senha_temporaria),
            perfil=perfil,
            ativo=True,
            deve_trocar_senha=True,
        )
        session.add(usuario)
        session.flush()
        _registrar(
            session,
            "criar_usuario",
            alvo=usuario.id,
            email=email_normalizado,
            perfil=perfil,
        )
        for empresa_codigo, centro_custo_id in centros:
            _conceder(session, usuario, empresa_codigo, centro_custo_id)
        return usuario.id, senha_temporaria


def redefinir_senha(usuario_id: int) -> str:
    exigir_controle_geral()
    if principal_atual().id == usuario_id:
        raise ValidationError({"usuario": "Use a troca de senha da sua própria conta."})
    senha_temporaria = secrets.token_urlsafe(18)
    with session_scope() as session:
        usuario = _usuario_ativo(session, usuario_id)
        usuario.senha_hash = hash_senha(senha_temporaria)
        usuario.deve_trocar_senha = True
        usuario.versao_sessao += 1
        usuario.tentativas_login = 0
        usuario.bloqueado_ate = None
        _registrar(session, "redefinir_senha", alvo=usuario.id)
        return senha_temporaria


def definir_usuario_ativo(usuario_id: int, ativo: bool) -> None:
    exigir_administrador_acessos()
    principal = principal_atual()
    if principal.id == usuario_id and not ativo:
        raise ValidationError({"usuario": "Não é possível desativar sua própria conta."})
    with session_scope() as session:
        usuario = _usuario_ativo(session, usuario_id)
        _exigir_pode_gerir_perfil(usuario.perfil)
        if ativo:
            dominio_email = usuario.email_normalizado.rsplit("@", 1)[1]
            if not session.scalar(
                select(DominioPermitido.id).where(
                    DominioPermitido.dominio == dominio_email,
                    DominioPermitido.ativo.is_(True),
                )
            ):
                raise ValidationError({"usuario": "Ative o domínio autorizado antes de reativar esta conta."})
        if not ativo:
            _manter_um_controle_geral(session, usuario, "usuario")
        usuario.ativo = ativo
        usuario.versao_sessao += 1
        _registrar(session, "ativar_usuario" if ativo else "desativar_usuario", alvo=usuario.id)


def alterar_perfil(usuario_id: int, perfil: str) -> None:
    exigir_administrador_acessos()
    if perfil not in PERFIS:
        raise ValidationError({"perfil": "Perfil inválido."})
    _exigir_pode_gerir_perfil(perfil)
    with session_scope() as session:
        usuario = _usuario_ativo(session, usuario_id)
        _exigir_pode_gerir_perfil(usuario.perfil)
        if perfil != PERFIL_CONTROLE_GERAL:
            _manter_um_controle_geral(session, usuario, "perfil")
        anterior = usuario.perfil
        usuario.perfil = perfil
        usuario.versao_sessao += 1
        _registrar(session, "alterar_perfil", alvo=usuario.id, anterior=anterior, novo=perfil)


def listar_acessos(usuario_id: int) -> list[AcessoResumo]:
    exigir_administrador_acessos()
    with session_scope() as session:
        _usuario_ativo(session, usuario_id)
        acessos = session.scalars(
            select(AcessoCentroCusto).where(AcessoCentroCusto.usuario_id == usuario_id)
        ).all()
        resultado = []
        for acesso in acessos:
            if acesso.asap_centro_custo_id is not None:
                centro = session.get(AsapCentroCusto, acesso.asap_centro_custo_id)
                empresa = "ASAP"
            else:
                centro = session.get(SuperusCentroCusto, acesso.superus_centro_custo_id)
                empresa = "SUPERUS"
            if centro is not None:
                resultado.append(AcessoResumo(acesso.id, empresa, centro.id, centro.titulo))
        return sorted(resultado, key=lambda a: (a.empresa, a.titulo.casefold()))


def listar_centros_custo(empresa_codigo: str):
    exigir_administrador_acessos()
    if empresa_codigo == "ASAP":
        modelo = AsapCentroCusto
    elif empresa_codigo == "SUPERUS":
        modelo = SuperusCentroCusto
    else:
        raise ValidationError({"empresa": "Empresa inválida."})
    with session_scope() as session:
        return list(session.scalars(select(modelo).order_by(modelo.titulo)))


def _conceder(session, usuario: Usuario, empresa_codigo: str, centro_custo_id: int) -> None:
    if empresa_codigo == "ASAP":
        modelo = AsapCentroCusto
        atributo = "asap_centro_custo_id"
    elif empresa_codigo == "SUPERUS":
        modelo = SuperusCentroCusto
        atributo = "superus_centro_custo_id"
    else:
        raise ValidationError({"empresa": "Empresa inválida."})

    centro = session.get(modelo, centro_custo_id)
    if centro is None:
        raise NotFoundError("Centro de custo não encontrado.")
    if session.scalar(
        select(AcessoCentroCusto.id).where(
            AcessoCentroCusto.usuario_id == usuario.id,
            getattr(AcessoCentroCusto, atributo) == centro_custo_id,
        )
    ):
        raise ValidationError({"centro_custo": "O usuário já tem acesso a este centro de custo."})

    empresa = session.scalar(select(Empresa).where(Empresa.codigo == empresa_codigo))
    if empresa is None or centro.empresa_id != empresa.id:
        raise ValidationError({"centro_custo": "O centro de custo não corresponde à empresa."})
    session.add(
        AcessoCentroCusto(
            usuario_id=usuario.id,
            empresa_id=empresa.id,
            **{atributo: centro_custo_id},
        )
    )
    _registrar(
        session,
        "conceder_acesso",
        alvo=usuario.id,
        empresa=empresa_codigo,
        centro_custo_id=centro_custo_id,
    )


def conceder_acesso(usuario_id: int, empresa_codigo: str, centro_custo_id: int) -> None:
    exigir_administrador_acessos()
    with session_scope() as session:
        usuario = _usuario_ativo(session, usuario_id)
        _conceder(session, usuario, empresa_codigo, centro_custo_id)
        usuario.versao_sessao += 1


def revogar_acesso(usuario_id: int, acesso_id: int) -> None:
    exigir_administrador_acessos()
    with session_scope() as session:
        acesso = session.get(AcessoCentroCusto, acesso_id)
        if acesso is None or acesso.usuario_id != usuario_id:
            raise NotFoundError("Concessão de acesso não encontrada.")
        usuario = _usuario_ativo(session, usuario_id)
        detalhes = {
            "empresa": "ASAP" if acesso.asap_centro_custo_id is not None else "SUPERUS",
            "centro_custo_id": acesso.asap_centro_custo_id or acesso.superus_centro_custo_id,
        }
        session.delete(acesso)
        usuario.versao_sessao += 1
        _registrar(session, "revogar_acesso", alvo=usuario.id, **detalhes)


def listar_auditoria(limite: int = 100) -> list[AuditoriaAcesso]:
    exigir_administrador_acessos()
    with session_scope() as session:
        return list(
            session.scalars(
                select(AuditoriaAcesso).order_by(AuditoriaAcesso.criado_em.desc()).limit(limite)
            )
        )


# ------------------------------------------------------ solicitações ----


MSG_DOMINIO_NAO_AUTORIZADO = (
    "O domínio {dominio} não está autorizado a solicitar acesso ao SIM. "
    "Use o seu e-mail corporativo; em caso de dúvida, fale com o administrador do SIM."
)


def solicitar_acesso(
    nome: str,
    email: str,
    senha: str,
    confirmacao: str,
    perfil: str,
    centro_custo_informado: str,
) -> None:
    """Registra um pedido de conta. Pública: chamada na tela de login, sem usuário autenticado.

    Se o e-mail já tem conta ou pedido em aberto, nada é gravado e a resposta é a mesma,
    para a tela não revelar quais e-mails estão cadastrados.
    """
    erros: dict[str, str] = {}
    nome_normalizado = (nome or "").strip()
    if not nome_normalizado or len(nome_normalizado) > 255:
        erros["nome"] = "Informe um nome (até 255 caracteres)."
    try:
        email_normalizado = normalizar_email(email)
    except ValidationError as exc:
        erros.update(exc.errors)
    else:
        with session_scope() as session:
            if not _dominio_ativo(session, email_normalizado):
                erros["email"] = MSG_DOMINIO_NAO_AUTORIZADO.format(dominio=email_normalizado.rsplit("@", 1)[1])
    try:
        validar_senha(senha, confirmacao)
    except ValidationError as exc:
        erros.update(exc.errors)
    if perfil not in PERFIS:
        erros["perfil"] = "Escolha uma classificação."
    centro = (centro_custo_informado or "").strip()
    if not centro:
        erros["centro_custo"] = "Informe o centro de custo do contrato."
    elif len(centro) > 1000:
        erros["centro_custo"] = "Use no máximo 1000 caracteres."
    if erros:
        raise ValidationError(erros)

    try:
        _registrar_solicitacao(nome_normalizado, email, email_normalizado, senha, perfil, centro)
    except IntegrityError:
        # Outro pedido em aberto para o mesmo e-mail foi gravado ao mesmo tempo (índice único de
        # pendentes); a resposta é a mesma de quando o pedido já existia.
        return


def _registrar_solicitacao(
    nome: str, email: str, email_normalizado: str, senha: str, perfil: str, centro: str
) -> None:
    with session_scope() as session:
        if session.scalar(select(Usuario.id).where(Usuario.email_normalizado == email_normalizado)):
            return
        if session.scalar(
            select(SolicitacaoAcesso.id).where(
                SolicitacaoAcesso.email_normalizado == email_normalizado,
                SolicitacaoAcesso.status == STATUS_PENDENTE,
            )
        ):
            return
        pendentes = session.scalar(
            select(func.count(SolicitacaoAcesso.id)).where(SolicitacaoAcesso.status == STATUS_PENDENTE)
        )
        if pendentes >= _MAX_SOLICITACOES_PENDENTES:
            raise ValidationError(
                {"email": "Não foi possível registrar o pedido agora. Contate o administrador do SIM."}
            )
        session.add(
            SolicitacaoAcesso(
                nome=nome,
                email=email.strip(),
                email_normalizado=email_normalizado,
                senha_hash=hash_senha(senha),
                perfil_solicitado=perfil,
                centro_custo_informado=centro,
                status=STATUS_PENDENTE,
            )
        )


def contar_solicitacoes_pendentes() -> int:
    exigir_administrador_acessos()
    with session_scope() as session:
        return session.scalar(
            select(func.count(SolicitacaoAcesso.id)).where(SolicitacaoAcesso.status == STATUS_PENDENTE)
        )


def listar_solicitacoes(status: str | None = None) -> list[SolicitacaoAcesso]:
    exigir_administrador_acessos()
    with session_scope() as session:
        consulta = select(SolicitacaoAcesso)
        if status is not None:
            consulta = consulta.where(SolicitacaoAcesso.status == status)
        if status == STATUS_PENDENTE:
            ordem = SolicitacaoAcesso.criado_em.asc()
        else:
            ordem = SolicitacaoAcesso.criado_em.desc()
        return list(session.scalars(consulta.order_by(ordem, SolicitacaoAcesso.id)))


def _dominio_ativo(session, email_normalizado: str) -> bool:
    dominio = email_normalizado.rsplit("@", 1)[1]
    return bool(
        session.scalar(
            select(DominioPermitido.id).where(
                DominioPermitido.dominio == dominio,
                DominioPermitido.ativo.is_(True),
            )
        )
    )


def dominio_autorizado(email_normalizado: str) -> bool:
    exigir_administrador_acessos()
    with session_scope() as session:
        return _dominio_ativo(session, email_normalizado)


def _solicitacao_pendente(session, solicitacao_id: int) -> SolicitacaoAcesso:
    solicitacao = session.get(SolicitacaoAcesso, solicitacao_id)
    if solicitacao is None:
        raise NotFoundError("Solicitação não encontrada.")
    if solicitacao.status != STATUS_PENDENTE:
        raise ValidationError({"solicitacao": "Esta solicitação já foi decidida."})
    return solicitacao


def aprovar_solicitacao(
    solicitacao_id: int,
    perfil: str,
    centros: list[tuple[str, int]] | None = None,
    parecer: str = "",
) -> int:
    """Cria a conta com a senha escolhida pelo solicitante e libera os centros indicados.

    O aprovador decide o perfil final (pode ser diferente do pedido). Os centros só se
    aplicam ao perfil de usuário de obra. O domínio do e-mail precisa estar autorizado: a aprovação
    não autoriza domínios (isso fica na lista de domínios, para um erro de digitação não virar acesso).
    """
    exigir_administrador_acessos()
    if perfil not in PERFIS:
        raise ValidationError({"perfil": "Perfil inválido."})
    _exigir_pode_gerir_perfil(perfil)
    centros = list(dict.fromkeys(centros or [])) if perfil == PERFIL_USUARIO else []
    with session_scope() as session:
        solicitacao = _solicitacao_pendente(session, solicitacao_id)
        if session.scalar(
            select(Usuario.id).where(Usuario.email_normalizado == solicitacao.email_normalizado)
        ):
            raise ValidationError({"email": "Já existe uma conta para este e-mail. Recuse esta solicitação."})

        if not _dominio_ativo(session, solicitacao.email_normalizado):
            dominio = solicitacao.email_normalizado.rsplit("@", 1)[1]
            raise ValidationError(
                {"email": f"O domínio {dominio} não está autorizado. Recuse esta solicitação ou, se o domínio "
                          "for legítimo, autorize-o em Domínios autorizados antes de aprovar."}
            )

        usuario = Usuario(
            email=solicitacao.email,
            email_normalizado=solicitacao.email_normalizado,
            nome=solicitacao.nome,
            senha_hash=solicitacao.senha_hash,
            perfil=perfil,
            ativo=True,
            deve_trocar_senha=False,
        )
        session.add(usuario)
        session.flush()
        _registrar(
            session,
            "aprovar_solicitacao",
            alvo=usuario.id,
            solicitacao_id=solicitacao.id,
            email=solicitacao.email_normalizado,
            perfil_solicitado=solicitacao.perfil_solicitado,
            perfil=perfil,
        )
        for empresa_codigo, centro_custo_id in centros:
            _conceder(session, usuario, empresa_codigo, centro_custo_id)

        solicitacao.status = STATUS_APROVADA
        solicitacao.parecer = (parecer or "").strip() or None
        solicitacao.decidido_por_id = principal_atual().id
        solicitacao.decidido_em = utcnow()
        solicitacao.usuario_id = usuario.id
        solicitacao.senha_hash = None
        return usuario.id


def recusar_solicitacao(solicitacao_id: int, parecer: str) -> None:
    exigir_administrador_acessos()
    parecer = (parecer or "").strip()
    if not parecer:
        raise ValidationError({"parecer": "Escreva o motivo da recusa."})
    with session_scope() as session:
        solicitacao = _solicitacao_pendente(session, solicitacao_id)
        solicitacao.status = STATUS_RECUSADA
        solicitacao.parecer = parecer
        solicitacao.decidido_por_id = principal_atual().id
        solicitacao.decidido_em = utcnow()
        solicitacao.senha_hash = None
        _registrar(
            session,
            "recusar_solicitacao",
            solicitacao_id=solicitacao.id,
            email=solicitacao.email_normalizado,
        )
