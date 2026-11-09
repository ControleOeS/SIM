"""Administração de usuários, domínios e permissões do SIM."""
from __future__ import annotations

import streamlit as st

from sim import access_admin
from sim.auth import (
    PERFIL_FATURAMENTO,
    PERFIL_USUARIO,
    PERFIS_CONTROLE,
    PERFIS_TODAS_OBRAS,
    principal_atual,
)
from sim.errors import SimError
from sim.formatters import formatar_data_hora
from sim.ui.layout import topo
from sim.ui.navegacao import NOME_EMPRESA

topo(["O&S Gestão", "Controle de acesso"])
st.title("Controle de acesso")
st.caption("Contas, domínios autorizados e permissões por centro de custo.")
st.warning(
    "Ninguém visualiza senhas atuais. A senha temporária (criação de conta ou redefinição pelo Controle Geral) "
    "é exibida uma única vez e deve ser entregue ao usuário por canal seguro. "
    "Antes de criar uma conta, confirme a identidade e o e-mail por um canal independente."
)

# Controle aprova acessos, cria contas, libera centros e desativa contas, mas não mexe em domínios,
# senhas nem em contas de nível Controle; o Controle Geral faz tudo (regras também nos serviços).
CONTROLE_GERAL = principal_atual().controle_geral
PERFIS_PERMITIDOS = [p for p in access_admin.ROTULOS_PERFIL if CONTROLE_GERAL or p not in PERFIS_CONTROLE]


def _executar(acao, mensagem: str) -> bool:
    try:
        acao()
    except SimError as exc:
        st.error(exc.descricao())
        return False
    st.success(mensagem)
    return True


def _rotulo_centro(centro) -> str:
    """Título do centro; na SUPERUS, também a coligada (Superus Engenharia, ACPL ou Superus Holding)."""
    coligada = getattr(centro, "coligada", None)
    encerrado = "" if centro.ativo else " · ENCERRADO"
    return f"{centro.titulo} · {coligada}{encerrado}" if coligada else f"{centro.titulo}{encerrado}"


def _explicar_perfil(perfil: str) -> None:
    if perfil in PERFIS_TODAS_OBRAS:
        st.caption("Esta classificação acessa todas as obras; não é preciso escolher centros de custo.")
    elif perfil == PERFIL_FATURAMENTO:
        st.caption("Faturamento acessa só a área administrativa, com todas as obras da ASAP e da SUPERUS.")


def _opcoes_centros() -> dict[tuple[str, int], str]:
    opcoes = {}
    for empresa_codigo in ("ASAP", "SUPERUS"):
        for centro in access_admin.listar_centros_custo(empresa_codigo):
            opcoes[(empresa_codigo, centro.id)] = f"{empresa_codigo} · {_rotulo_centro(centro)}"
    return opcoes


st.subheader("Solicitações de acesso")
pendentes = access_admin.listar_solicitacoes(access_admin.STATUS_PENDENTE)
if not pendentes:
    st.caption("Nenhuma solicitação aguardando aprovação.")
else:
    st.info(f"{len(pendentes)} solicitação(ões) aguardando sua análise.")
    centros_disponiveis = _opcoes_centros()
    for solicitacao in pendentes:
        with st.container(border=True):
            st.markdown(f"**{solicitacao.nome}** · {solicitacao.email}")
            st.caption(f"Pedido em {formatar_data_hora(solicitacao.criado_em)} (horário de Brasília)")
            col_pedido, col_cc = st.columns(2)
            col_pedido.markdown(
                f"**Classificação pedida**  \n{access_admin.ROTULOS_PERFIL[solicitacao.perfil_solicitado]}"
            )
            col_cc.markdown("**Centro de custo informado pelo solicitante**")
            col_cc.code(solicitacao.centro_custo_informado, language=None, wrap_lines=True)
            if not access_admin.dominio_autorizado(solicitacao.email_normalizado):
                dominio = solicitacao.email_normalizado.rsplit("@", 1)[1]
                st.error(
                    f"O domínio **{dominio}** não está autorizado, então esta solicitação não pode ser aprovada. "
                    "Recuse-a ou, se o domínio for legítimo, autorize-o em Domínios autorizados antes de aprovar."
                )

            pedido_permitido = solicitacao.perfil_solicitado in PERFIS_PERMITIDOS
            if not pedido_permitido:
                st.caption("Classificações Controle e Controle Geral só podem ser concedidas pelo Controle Geral.")
            perfil_final = st.selectbox(
                "Classificação a conceder",
                PERFIS_PERMITIDOS,
                index=PERFIS_PERMITIDOS.index(solicitacao.perfil_solicitado) if pedido_permitido else None,
                format_func=access_admin.ROTULOS_PERFIL.get,
                placeholder="Escolha a classificação",
                key=f"solic-perfil-{solicitacao.id}",
            )
            centros_escolhidos: list[tuple[str, int]] = []
            if perfil_final == PERFIL_USUARIO:
                if centros_disponiveis:
                    centros_escolhidos = st.multiselect(
                        "Centros de custo a liberar",
                        list(centros_disponiveis),
                        format_func=centros_disponiveis.get,
                        key=f"solic-centros-{solicitacao.id}",
                        help="Compare com o centro de custo informado pelo solicitante.",
                    )
                else:
                    st.caption(
                        "Não há centros de custo cadastrados. A conta pode ser aprovada agora e os centros "
                        "liberados depois, em Usuários e permissões."
                    )
            else:
                _explicar_perfil(perfil_final)
            parecer = st.text_area(
                "Parecer do aprovador",
                key=f"solic-parecer-{solicitacao.id}",
                placeholder="Comentários sobre o pedido. Obrigatório para recusar.",
            )
            col_aprovar, col_recusar = st.columns(2)
            if col_aprovar.button("Aprovar", type="primary", key=f"solic-aprovar-{solicitacao.id}",
                                  disabled=perfil_final is None):
                if _executar(
                    lambda: access_admin.aprovar_solicitacao(
                        solicitacao.id, perfil_final, centros_escolhidos, parecer
                    ),
                    "aprovar a solicitação",
                ):
                    st.rerun()
            if col_recusar.button("Recusar", key=f"solic-recusar-{solicitacao.id}"):
                if _executar(
                    lambda: access_admin.recusar_solicitacao(solicitacao.id, parecer),
                    "recusar a solicitação",
                ):
                    st.rerun()

with st.expander("Histórico de solicitações"):
    decididas = [
        s for s in access_admin.listar_solicitacoes() if s.status != access_admin.STATUS_PENDENTE
    ]
    if not decididas:
        st.caption("Nenhuma solicitação decidida ainda.")
    else:
        st.dataframe(
            [
                {
                    "Pedido em": formatar_data_hora(s.criado_em),
                    "Nome": s.nome,
                    "E-mail": s.email,
                    "CC informado": s.centro_custo_informado,
                    "Classificação pedida": access_admin.ROTULOS_PERFIL[s.perfil_solicitado],
                    "Situação": s.status.capitalize(),
                    "Parecer": s.parecer or "",
                    "Decidido em": formatar_data_hora(s.decidido_em),
                }
                for s in decididas
            ],
            hide_index=True,
            use_container_width=True,
        )

st.divider()

with st.expander("Domínios autorizados", expanded=True):
    dominios = access_admin.listar_dominios()
    st.caption("Só e-mails destes domínios podem pedir ou receber conta. Um domínio autorizado não cria contas.")
    if not CONTROLE_GERAL:
        st.caption("Somente o Controle Geral adiciona ou desativa domínios.")
    for dominio in dominios:
        col_nome, col_acao = st.columns([4, 1])
        col_nome.write(f"{dominio.dominio} — {'Ativo' if dominio.ativo else 'Inativo'}")
        if CONTROLE_GERAL and dominio.ativo and col_acao.button("Desativar", key=f"dominio-desativar-{dominio.id}"):
            if _executar(lambda: access_admin.desativar_dominio(dominio.id), "desativar o domínio"):
                st.rerun()

    if CONTROLE_GERAL:
        with st.form("novo-dominio"):
            dominio_novo = st.text_input("Adicionar domínio")
            adicionar = st.form_submit_button("Autorizar domínio")
        if adicionar and _executar(lambda: access_admin.adicionar_dominio(dominio_novo), "autorizar o domínio"):
            st.rerun()

st.divider()
st.subheader("Criar usuário")
# Sem st.form: a coligada e os centros de custo aparecem conforme o perfil e a coligada escolhidos.
# Após criar, a versão das chaves muda e o formulário volta vazio; a senha aparece uma única vez.
_v = st.session_state.setdefault("_novo_usuario_v", 0)
_senha_criada = st.session_state.pop("_novo_usuario_senha", None)
if _senha_criada:
    st.success("Conta criada. Copie e entregue a senha temporária ao usuário por canal seguro.")
    st.code(_senha_criada)
with st.container(border=True):
    nome = st.text_input("Nome", key=f"novo-usuario-nome-{_v}")
    email = st.text_input("E-mail", key=f"novo-usuario-email-{_v}")
    perfil = st.selectbox(
        "Perfil inicial",
        PERFIS_PERMITIDOS,
        format_func=access_admin.ROTULOS_PERFIL.get,
        key=f"novo-usuario-perfil-{_v}",
    )
    _explicar_perfil(perfil)
    centros_novo: list[tuple[str, int]] = []
    if perfil == PERFIL_USUARIO:
        coligada = st.selectbox(
            "Coligada",
            list(NOME_EMPRESA),
            format_func=NOME_EMPRESA.get,
            index=None,
            placeholder="Selecione a coligada",
            key=f"novo-usuario-coligada-{_v}",
        )
        if coligada is not None:
            centros_coligada = {c.id: _rotulo_centro(c) for c in access_admin.listar_centros_custo(coligada)}
            if not centros_coligada:
                st.caption(f"Nenhum centro de custo cadastrado em {NOME_EMPRESA[coligada]}.")
            ids = st.multiselect(
                "Centros de custo com acesso",
                list(centros_coligada),
                format_func=centros_coligada.get,
                placeholder="Selecione o(s) centro(s) de custo",
                key=f"novo-usuario-centros-{_v}-{coligada}",
                help="O usuário de obra só verá os BMs dos centros escolhidos. Outros centros, inclusive de "
                     "outra coligada, podem ser liberados depois em Usuários e permissões.",
            )
            centros_novo = [(coligada, i) for i in ids]
    criar = st.button("Criar conta", type="primary", key=f"novo-usuario-criar-{_v}")

if criar:
    try:
        _, senha_temporaria = access_admin.criar_usuario(email, nome, perfil, centros_novo)
    except SimError as exc:
        st.error(exc.descricao())
    else:
        st.session_state["_novo_usuario_senha"] = senha_temporaria
        st.session_state["_novo_usuario_v"] = _v + 1
        st.rerun()

st.divider()
st.subheader("Usuários e permissões")
usuarios = access_admin.listar_usuarios()
if not usuarios:
    st.info("Nenhum usuário cadastrado.")
else:
    usuario_por_id = {u.id: u for u in usuarios}
    selecionado_id = st.selectbox(
        "Usuário",
        list(usuario_por_id),
        format_func=lambda user_id: (
            f"{usuario_por_id[user_id].nome} · {usuario_por_id[user_id].email} "
            f"({'ativo' if usuario_por_id[user_id].ativo else 'inativo'})"
        ),
    )
    usuario = usuario_por_id[selecionado_id]

    # Contas de nível Controle só são alteradas pelo Controle Geral.
    gerenciavel = CONTROLE_GERAL or usuario.perfil not in PERFIS_CONTROLE
    if not gerenciavel:
        st.info("Esta conta tem perfil Controle ou Controle Geral; somente o Controle Geral pode alterá-la.")
    c1, c2 = st.columns(2)
    with c1:
        opcoes_perfil = PERFIS_PERMITIDOS if gerenciavel else list(access_admin.ROTULOS_PERFIL)
        novo_perfil = st.selectbox(
            "Perfil",
            opcoes_perfil,
            index=opcoes_perfil.index(usuario.perfil) if usuario.perfil in opcoes_perfil else None,
            format_func=access_admin.ROTULOS_PERFIL.get,
            disabled=not gerenciavel,
            key=f"perfil-{usuario.id}",
        )
        if st.button("Salvar perfil", key=f"salvar-perfil-{usuario.id}", disabled=not gerenciavel):
            if _executar(lambda: access_admin.alterar_perfil(usuario.id, novo_perfil), "alterar o perfil"):
                st.rerun()
    with c2:
        propria_conta = usuario.id == principal_atual().id
        rotulo = "Desativar conta" if usuario.ativo else "Reativar conta"
        if st.button(rotulo, key=f"ativo-{usuario.id}", disabled=propria_conta or not gerenciavel,
                     help="Não é possível desativar a própria conta." if propria_conta else None):
            if _executar(
                lambda: access_admin.definir_usuario_ativo(usuario.id, not usuario.ativo),
                "alterar o estado da conta",
            ):
                st.rerun()
        if CONTROLE_GERAL and st.button("Redefinir senha", key=f"reset-senha-{usuario.id}", disabled=propria_conta):
            try:
                senha_temporaria = access_admin.redefinir_senha(usuario.id)
                st.success("Senha temporária gerada. Entregue-a ao usuário por canal seguro.")
                st.code(senha_temporaria)
            except SimError as exc:
                st.error(exc.descricao())
        if propria_conta:
            st.caption("Esta é a sua conta. Para mudar a sua senha, use **Trocar senha** na barra lateral.")

    if usuario.perfil in PERFIS_TODAS_OBRAS:
        st.info("Este perfil já acessa todas as obras; não há centros de custo para liberar.")
    elif usuario.perfil == PERFIL_FATURAMENTO:
        st.info("Faturamento acessa só a área administrativa, com todas as obras da ASAP e da SUPERUS.")
    elif usuario.perfil == PERFIL_USUARIO:
        acessos = access_admin.listar_acessos(usuario.id)
        st.markdown("**Centros de custo concedidos**")
        if not acessos:
            st.caption("Este usuário ainda não tem acesso a centros de custo.")
        for acesso in acessos:
            col_acesso, col_revogar = st.columns([4, 1])
            col_acesso.write(f"{acesso.empresa} · {acesso.titulo}")
            if col_revogar.button("Revogar", key=f"revogar-{usuario.id}-{acesso.id}"):
                if _executar(
                    lambda: access_admin.revogar_acesso(usuario.id, acesso.id),
                    "revogar o acesso",
                ):
                    st.rerun()

        empresa_codigo = st.selectbox("Empresa", ["ASAP", "SUPERUS"], key=f"empresa-{usuario.id}")
        centros = access_admin.listar_centros_custo(empresa_codigo)
        if centros:
            centro_id = st.selectbox(
                "Centro de custo",
                [c.id for c in centros],
                format_func=lambda id_: next(c.titulo for c in centros if c.id == id_),
                key=f"centro-{usuario.id}-{empresa_codigo}",
            )
            if st.button("Conceder acesso", key=f"conceder-{usuario.id}-{empresa_codigo}"):
                if _executar(
                    lambda: access_admin.conceder_acesso(usuario.id, empresa_codigo, centro_id),
                    "conceder o acesso",
                ):
                    st.rerun()
        else:
            st.caption("Não há centros de custo cadastrados para esta empresa.")

with st.expander("Auditoria administrativa"):
    auditoria = access_admin.listar_auditoria()
    nomes = {u.id: f"{u.nome} · {u.email}" for u in usuarios}

    def _quem(usuario_id: int | None) -> str:
        if usuario_id is None:
            return ""
        return nomes.get(usuario_id, f"Usuário #{usuario_id}")

    st.dataframe(
        [
            {
                "Data": formatar_data_hora(item.criado_em),
                "Realizado por": _quem(item.ator_usuario_id),
                "Ação": item.acao,
                "Usuário afetado": _quem(item.alvo_usuario_id),
                "Detalhes": item.detalhes,
            }
            for item in auditoria
        ],
        hide_index=True,
        use_container_width=True,
    )
