"""Interface de login e troca obrigatória de senha."""
from __future__ import annotations

import streamlit as st

from sim.auth import (
    autenticar,
    carregar_principal,
    configuracao_exige_codigo,
    criar_primeiro_administrador,
    deve_trocar_senha,
    existe_administrador_inicializado,
    existe_algum_usuario,
    trocar_senha,
    usando_principal,
)
from sim import redefinicao_senha
from sim.access_admin import ROTULOS_PERFIL, solicitar_acesso
from sim.errors import SimError, ValidationError
from sim.ui.tema import NOME_SISTEMA, caminho_logo

_ID_USUARIO = "_sim_usuario_id"
_VERSAO_SESSAO = "_sim_versao_sessao"
_SOLICITACAO_ENVIADA = "_sim_solicitacao_enviada"
_REDEFINICAO_EMAIL = "_sim_redefinicao_email"
_SENHA_REDEFINIDA = "_sim_senha_redefinida"


def sair() -> None:
    st.session_state.pop(_ID_USUARIO, None)
    st.session_state.pop(_VERSAO_SESSAO, None)
    st.rerun()


def _pagina_configuracao_inicial() -> None:
    st.subheader("Configuração inicial")
    st.info(
        "Nenhum usuário foi cadastrado ainda. Crie a conta do administrador do SIM. "
        "Depois disso, esta tela deixa de aparecer e novas contas são criadas no painel Controle de acesso."
    )
    with st.form("sim-primeiro-admin"):
        codigo = ""
        if configuracao_exige_codigo():
            codigo = st.text_input("Código de configuração", type="password",
                                   help="Definido pelo responsável técnico na configuração da hospedagem.")
        nome = st.text_input("Nome", autocomplete="name")
        email = st.text_input("E-mail", autocomplete="username")
        senha = st.text_input("Senha (mínimo 8 caracteres)", type="password", autocomplete="new-password")
        confirmacao = st.text_input("Confirme a senha", type="password", autocomplete="new-password")
        enviar = st.form_submit_button("Criar administrador", type="primary", width="stretch")
    if enviar:
        try:
            resultado = criar_primeiro_administrador(email, nome, senha, confirmacao, codigo)
        except ValidationError as exc:
            st.error(exc.message)
            for mensagem in exc.errors.values():
                st.markdown(f"- {mensagem}")
            return
        except SimError as exc:
            st.error(exc.message)
            return
        st.session_state[_ID_USUARIO], st.session_state[_VERSAO_SESSAO] = resultado
        st.rerun()


def _pagina_login() -> None:
    st.image(str(caminho_logo("OES")), width=150)
    st.title(NOME_SISTEMA)
    if not existe_algum_usuario():
        _pagina_configuracao_inicial()
        return
    aba_entrar, aba_solicitar, aba_redefinir = st.tabs(["Entrar", "Solicitar acesso", "Esqueci a senha"])
    with aba_entrar:
        _formulario_entrar()
    with aba_solicitar:
        _formulario_solicitacao()
    with aba_redefinir:
        _formulario_redefinicao()


def _formulario_redefinicao() -> None:
    if not redefinicao_senha.disponivel():
        st.info(
            "A redefinição por e-mail ainda não está configurada. "
            "Peça a um administrador do SIM para redefinir sua senha."
        )
        return
    if st.session_state.get(_SENHA_REDEFINIDA):
        st.success("Senha redefinida. Entre na aba Entrar com a nova senha.")
        if st.button("Redefinir outra senha", key="sim-redefinir-de-novo"):
            st.session_state.pop(_SENHA_REDEFINIDA, None)
            st.rerun()
        return

    email_enviado = st.session_state.get(_REDEFINICAO_EMAIL)
    if not email_enviado:
        st.caption("Informe o e-mail da sua conta. Enviaremos um código de 6 dígitos para criar uma nova senha.")
        with st.form("sim-redefinir-email"):
            email = st.text_input("E-mail da conta", autocomplete="email")
            enviar = st.form_submit_button("Enviar código", type="primary", width="stretch")
        if enviar:
            try:
                redefinicao_senha.solicitar_codigo(email)
            except ValidationError as exc:
                st.error(next(iter(exc.errors.values()), exc.message))
                return
            st.session_state[_REDEFINICAO_EMAIL] = email.strip()
            st.rerun()
        return

    st.info(
        f"Se **{email_enviado}** tiver uma conta ativa, enviamos um código para ele. "
        "Confira também a caixa de spam. O código vale por 15 minutos."
    )
    with st.form("sim-redefinir-codigo"):
        codigo = st.text_input("Código recebido", max_chars=6, autocomplete="one-time-code")
        nova = st.text_input("Nova senha (mínimo 8 caracteres)", type="password", autocomplete="new-password")
        confirmacao = st.text_input("Confirme a nova senha", type="password", autocomplete="new-password")
        salvar = st.form_submit_button("Redefinir senha", type="primary", width="stretch")
    if salvar:
        try:
            redefinicao_senha.redefinir_com_codigo(email_enviado, codigo, nova, confirmacao)
        except ValidationError as exc:
            st.error(exc.message)
            for mensagem in exc.errors.values():
                st.markdown(f"- {mensagem}")
            return
        st.session_state.pop(_REDEFINICAO_EMAIL, None)
        st.session_state[_SENHA_REDEFINIDA] = True
        st.rerun()
    if st.button("Usar outro e-mail ou pedir novo código", key="sim-redefinir-voltar"):
        st.session_state.pop(_REDEFINICAO_EMAIL, None)
        st.rerun()


def _formulario_solicitacao() -> None:
    if st.session_state.get(_SOLICITACAO_ENVIADA):
        st.success(
            "Solicitação enviada. Um aprovador vai analisar o pedido. Assim que for aprovado, "
            "entre na aba Entrar com o e-mail e a senha que você cadastrou."
        )
        if st.button("Fazer outra solicitação", key="sim-nova-solicitacao"):
            st.session_state.pop(_SOLICITACAO_ENVIADA, None)
            st.rerun()
        return

    st.caption("Preencha seus dados. O acesso só é liberado depois da aprovação de um administrador.")
    with st.form("sim-solicitar-acesso"):
        nome = st.text_input("Nome completo", autocomplete="name")
        email = st.text_input("E-mail", autocomplete="email")
        senha = st.text_input("Senha (mínimo 8 caracteres)", type="password", autocomplete="new-password")
        confirmacao = st.text_input("Confirme a senha", type="password", autocomplete="new-password")
        perfil = st.radio(
            "Classificação de acesso",
            list(ROTULOS_PERFIL),
            format_func=ROTULOS_PERFIL.get,
        )
        centro_custo = st.text_input(
            "Centro de custo do contrato",
            autocomplete="off",
            help="Escreva o centro de custo (código e/ou nome da obra) do contrato em que você trabalha.",
        )
        enviar = st.form_submit_button("Enviar solicitação", type="primary", width="stretch")
    if enviar:
        try:
            solicitar_acesso(nome, email, senha, confirmacao, perfil, centro_custo)
        except ValidationError as exc:
            st.error(exc.message)
            for mensagem in exc.errors.values():
                st.markdown(f"- {mensagem}")
            return
        except SimError as exc:
            st.error(exc.message)
            return
        st.session_state[_SOLICITACAO_ENVIADA] = True
        st.rerun()


def _formulario_entrar() -> None:
    if not existe_administrador_inicializado():
        st.error("O acesso ainda não foi inicializado.")
        st.markdown(
            "Um responsável técnico deve criar o primeiro administrador diretamente no servidor. "
            "Não existe cadastro público."
        )
        st.code(
            r'.\.venv\Scripts\python.exe -m sim.admin_cli criar-primeiro-admin email@dominio.com "Nome do administrador"',
            language="powershell",
        )
        return

    with st.form("sim-login"):
        email = st.text_input("E-mail", autocomplete="username")
        senha = st.text_input("Senha", type="password", autocomplete="current-password")
        enviar = st.form_submit_button("Entrar", type="primary", width="stretch")
    if enviar:
        resultado = autenticar(email, senha)
        if resultado is None:
            st.error("Não foi possível entrar. Confira seus dados ou contate o administrador.")
            return
        st.session_state[_ID_USUARIO], st.session_state[_VERSAO_SESSAO] = resultado
        st.rerun()
    st.caption("Ainda não tem conta? Use a aba **Solicitar acesso**; um administrador vai aprovar o pedido.")


def _pagina_troca_senha(principal) -> None:
    st.title("Defina sua senha")
    st.info("Por segurança, troque a senha temporária antes de continuar.")
    with st.form("sim-trocar-senha"):
        atual = st.text_input("Senha atual", type="password", autocomplete="current-password")
        nova = st.text_input("Nova senha", type="password", autocomplete="new-password")
        confirmacao = st.text_input("Confirme a nova senha", type="password", autocomplete="new-password")
        enviar = st.form_submit_button("Salvar senha", type="primary", width="stretch")
    if enviar and _gravar_nova_senha(principal, atual, nova, confirmacao):
        st.rerun()
    if st.button("Sair", key="sim-sair-troca-senha"):
        sair()


def _gravar_nova_senha(principal, atual: str, nova: str, confirmacao: str) -> bool:
    try:
        with usando_principal(principal):
            versao = trocar_senha(principal.id, atual, nova, confirmacao)
    except SimError as exc:
        st.error(exc.descricao())
        return False
    st.session_state[_VERSAO_SESSAO] = versao  # as demais sessões desta conta são encerradas
    return True


TROCA_SENHA_ABERTA = "_sim_troca_senha_aberta"


def _fechar_troca_senha() -> None:
    st.session_state.pop(TROCA_SENHA_ABERTA, None)


@st.dialog("Trocar senha", on_dismiss=_fechar_troca_senha)
def dialogo_trocar_senha(principal) -> None:
    """Troca voluntária da própria senha, a partir da barra lateral.

    Fica aberto enquanto TROCA_SENHA_ABERTA estiver na sessão (fecha ao salvar ou no X).
    """
    with st.form("sim-trocar-senha-voluntaria"):
        atual = st.text_input("Senha atual", type="password", autocomplete="current-password")
        nova = st.text_input("Nova senha (mínimo 8 caracteres)", type="password", autocomplete="new-password")
        confirmacao = st.text_input("Confirme a nova senha", type="password", autocomplete="new-password")
        enviar = st.form_submit_button("Salvar nova senha", type="primary", width="stretch")
    if enviar and _gravar_nova_senha(principal, atual, nova, confirmacao):
        _fechar_troca_senha()
        st.session_state.setdefault("_flash", []).append(("success", "Senha alterada."))
        st.rerun()


def usuario_autenticado():
    usuario_id = st.session_state.get(_ID_USUARIO)
    versao = st.session_state.get(_VERSAO_SESSAO)
    if not isinstance(usuario_id, int) or not isinstance(versao, int):
        st.session_state.pop(_ID_USUARIO, None)
        st.session_state.pop(_VERSAO_SESSAO, None)
        _pagina_login()
        return None

    principal = carregar_principal(usuario_id, versao)
    if principal is None:
        st.session_state.pop(_ID_USUARIO, None)
        st.session_state.pop(_VERSAO_SESSAO, None)
        st.warning("Sua sessão expirou ou o acesso foi alterado. Entre novamente.")
        _pagina_login()
        return None

    if deve_trocar_senha(principal.id):
        _pagina_troca_senha(principal)
        return None
    return principal
