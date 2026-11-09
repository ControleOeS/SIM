"""Testes de interface com o AppTest do Streamlit (sem navegador).

Cobrem: todas as telas abrem sem erro (banco vazio e com dados), o cadastro grava
pela tela, erros de validação mantêm o que foi digitado e a mensagem de sucesso
só aparece após a gravação.
Limitação: o AppTest não simula upload de arquivos nem clique em linhas de tabela;
esses fluxos são cobertos nos testes de serviço.
"""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from sim.auth import PERFIL_CONTROLE
from sim.database import session_scope
from sim.models import DominioPermitido, Usuario
from sim.services import asap, superus
from tests.conftest import arquivo
from tests.test_asap import CC as CC_ASAP, bm_dados
from tests.test_superus import CC as CC_SUP, mensal, semanal

APP = str(Path(__file__).resolve().parent.parent / "app.py")
TELAS = [
    "telas/inicio.py",
    "telas/adm_selecao.py",
    "telas/modulo_asap_eng.py",
    "telas/modulo_superus_eng.py",
    "telas/modulo_asap_adm.py",
    "telas/modulo_superus_adm.py",
    "telas/asap_eng_bm_mensal.py",
    "telas/asap_eng_cadastro.py",
    "telas/asap_adm_faturamento.py",
    "telas/superus_eng_bm_mensal.py",
    "telas/superus_eng_bm_semanal.py",
    "telas/superus_eng_cadastro.py",
    "telas/superus_eng_encerramento.py",
    "telas/asap_eng_encerramento.py",
    "telas/superus_eng_help.py",
    "telas/superus_adm_faturamento.py",
    "telas/superus_adm_planejamento.py",
    "telas/superus_adm_atualizar_dados.py",
    "telas/superus_adm_valor_previsto.py",
]


@pytest.fixture
def app(ambiente):
    st.cache_resource.clear()
    with session_scope() as session:
        dominio = DominioPermitido(dominio="empresa.test", ativo=True)
        usuario = Usuario(
            email="admin@empresa.test",
            email_normalizado="admin@empresa.test",
            nome="Administrador de teste",
            senha_hash="hash-nao-usado-no-teste",
            perfil=PERFIL_CONTROLE,
            ativo=True,
            deve_trocar_senha=False,
        )
        session.add_all([dominio, usuario])
        session.flush()
        usuario_id = usuario.id

    def abrir(tela: str = "telas/inicio.py") -> AppTest:
        at = AppTest.from_file(APP, default_timeout=30)
        at.session_state["_sim_usuario_id"] = usuario_id
        at.session_state["_sim_versao_sessao"] = 1
        at.run()
        if tela != "telas/inicio.py":
            at.switch_page(tela)
            at.run()
        return at

    return abrir


def _sem_erros(at: AppTest):
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("tela", TELAS)
def test_tela_abre_com_banco_vazio(app, tela):
    _sem_erros(app(tela))


@pytest.mark.parametrize("tela", TELAS)
def test_tela_abre_com_dados(app, tela):
    a = asap.criar_centro_custo(CC_ASAP)
    asap.criar_bm(bm_dados(a), [arquivo()])
    s = superus.criar_centro_custo(CC_SUP)
    superus.criar_bm_mensal(s, mensal(), [arquivo()])
    superus.criar_bm_semanal(s, semanal(), [arquivo()])
    _sem_erros(app(tela))


# ------------------------------------------------------------ navegação ----


def _links(at: AppTest, onde: str = "main") -> list[tuple[str, str]]:
    raiz = at.main if onde == "main" else at.sidebar
    return [(p.proto.label, p.proto.page) for p in raiz.get("page_link")]


def _html(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_inicio_tem_exatamente_tres_cartoes(app):
    at = app()
    _sem_erros(at)
    assert "Bem-vindo ao SIM" in _html(at)
    assert _links(at) == [("Acessar ASAP", "asap"), ("Acessar SUPERUS", "superus"),
                          ("Escolher empresa", "administrativo")]
    html = _html(at)
    assert 'alt="Logotipo ASAP"' in html and 'alt="Logotipo SUPERUS"' in html
    assert 'alt="Logotipo O&S Gestão"' in html


def test_administrativo_abre_selecao_de_empresa(app):
    at = app("telas/adm_selecao.py")
    _sem_erros(at)
    assert _links(at) == [("Abrir ASAP ADM", "asap-adm"), ("Abrir SUPERUS ADM", "superus-adm"),
                          ("Voltar à página inicial", "")]
    assert "O&amp;S Gestão<span>›</span><b>Administrativo</b>" in _html(at)


@pytest.mark.parametrize("tela, esperados", [
    ("telas/modulo_asap_eng.py", [("BM Mensal", "asap-bm-mensal"), ("Cadastro Centro de Custo", "asap-cadastro"),
                                  ("Encerramento", "asap-encerramento")]),
    ("telas/modulo_superus_eng.py", [("BM Mensal", "superus-bm-mensal"), ("BM Semanal", "superus-bm-semanal"),
                                     ("Cadastro Centro de Custo", "superus-cadastro"),
                                     ("Encerramento", "superus-encerramento"),
                                     ("Central de Ajuda", "superus-help")]),
    ("telas/modulo_asap_adm.py", [("Faturamento", "asap-faturamento")]),
    ("telas/modulo_superus_adm.py", [("Faturamento", "superus-faturamento"), ("Planejamento", "superus-planejamento"),
                                     ("Valor Previsto", "superus-valor-previsto"),
                                     ("Atualizar dados", "superus-atualizar-dados")]),
])
def test_modulo_abre_as_telas_corretas(app, tela, esperados):
    at = app(tela)
    _sem_erros(at)
    # os atalhos ficam em colunas (a ordem do DOM é por coluna); o que importa é o destino de cada um
    assert sorted(_links(at)) == sorted(esperados)


@pytest.mark.parametrize("tela, empresa, migalhas, lateral", [
    ("telas/asap_eng_bm_mensal.py", "ASAP", "O&amp;S Gestão<span>›</span>ASAP<span>›</span><b>BM Mensal</b>",
     ["", "controle-acesso", "asap", "asap-bm-mensal", "asap-cadastro", "asap-encerramento"]),
    ("telas/superus_eng_encerramento.py", "SUPERUS",
     "O&amp;S Gestão<span>›</span>SUPERUS<span>›</span><b>Encerramento</b>",
     ["", "controle-acesso", "superus", "superus-bm-mensal", "superus-bm-semanal", "superus-cadastro", "superus-encerramento",
      "superus-help"]),
    ("telas/asap_adm_faturamento.py", "ASAP",
     "O&amp;S Gestão<span>›</span>Administrativo<span>›</span>ASAP ADM<span>›</span><b>Faturamento</b>",
     ["", "controle-acesso", "administrativo", "asap-adm", "asap-faturamento"]),
    ("telas/superus_adm_planejamento.py", "SUPERUS",
     "O&amp;S Gestão<span>›</span>Administrativo<span>›</span>SUPERUS ADM<span>›</span><b>Planejamento</b>",
     ["", "controle-acesso", "administrativo", "superus-adm", "superus-faturamento", "superus-planejamento",
      "superus-valor-previsto", "superus-atualizar-dados"]),
])
def test_cabecalho_e_barra_lateral_por_modulo(app, tela, empresa, migalhas, lateral):
    """O&S sempre no cabeçalho; coligada correta; barra lateral só com telas do módulo atual."""
    at = app(tela)
    _sem_erros(at)
    html = _html(at)
    assert 'class="sim-topo__oes" alt="Logotipo O&S Gestão"' in html
    assert f'class="sim-topo__coligada" alt="Logotipo {empresa}"' in html
    outra = "SUPERUS" if empresa == "ASAP" else "ASAP"
    assert f'class="sim-topo__coligada" alt="Logotipo {outra}"' not in html
    assert migalhas in html
    assert [pagina for _, pagina in _links(at, "sidebar")] == lateral
    assert "Superus Engenharia" not in html and "Engenharia</span>" not in html


def test_falha_em_uma_tela_nao_impede_as_demais(app, monkeypatch):
    """Erro inesperado numa tela: mensagem com referência, barra lateral intacta, outras telas abrem."""
    from sim.services import asap as servico

    def quebrar(*a, **k):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(servico, "listar_centros_custo", quebrar)
    at = app("telas/asap_eng_bm_mensal.py")
    assert any("não pôde ser exibida" in e.value for e in at.error)
    # o traceback só aparece dentro do expansor "Detalhes técnicos", exibido pelo app.py
    detalhes = [x for x in at.expander if x.label == "Detalhes técnicos"]
    assert len(detalhes) == 1 and len(detalhes[0].exception) == 1
    assert len(at.exception) == 1
    assert [pag for _, pag in _links(at, "sidebar")] == [
        "", "controle-acesso", "asap", "asap-bm-mensal", "asap-cadastro", "asap-encerramento"
    ]

    at.switch_page("telas/superus_eng_cadastro.py").run()
    _sem_erros(at)
    assert not any("não pôde ser exibida" in e.value for e in at.error)
    assert "Cadastro de Centro de Custo" in [t.value for t in at.title]


def test_controle_de_acesso_so_abre_para_administrador(ambiente):
    from sim.auth import PERFIL_CONTROLE_GERAL

    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        usuario = Usuario(
            email="admin@empresa.test",
            email_normalizado="admin@empresa.test",
            nome="Administrador",
            senha_hash="hash-nao-usado-no-teste",
            perfil=PERFIL_CONTROLE_GERAL,
            ativo=True,
            deve_trocar_senha=False,
        )
        session.add(usuario)
        session.flush()
        usuario_id = usuario.id

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = usuario_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    _sem_erros(at)
    assert ("Controle de acesso", "controle-acesso") in _links(at, "sidebar")

    at.switch_page("telas/controle_acesso.py").run()
    _sem_erros(at)
    assert "Controle de acesso" in [t.value for t in at.title]


def test_login_local_e_conta_inicial_nao_configurada(ambiente):
    from sim.auth import PERFIL_CONTROLE_GERAL, hash_senha

    sem_usuarios = AppTest.from_file(APP, default_timeout=30).run()
    assert any(b.label == "Criar administrador" for b in sem_usuarios.button)

    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        session.add(
            Usuario(
                email="admin@empresa.test",
                email_normalizado="admin@empresa.test",
                nome="Administrador",
                senha_hash=hash_senha("senha-forte-para-teste-123"),
                perfil=PERFIL_CONTROLE_GERAL,
                ativo=True,
                deve_trocar_senha=False,
            )
        )

    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input[0].input("admin@empresa.test")
    at.text_input[1].input("senha-incorreta")
    next(button for button in at.button if button.label == "Entrar").click().run()
    assert any("Não foi possível entrar" in e.value for e in at.error)

    at.text_input[0].input("admin@empresa.test")
    at.text_input[1].input("senha-forte-para-teste-123")
    next(button for button in at.button if button.label == "Entrar").click().run()
    _sem_erros(at)
    assert ("Controle de acesso", "controle-acesso") in _links(at, "sidebar")


def test_exclusao_usa_botao_distinto(app):
    a = asap.criar_centro_custo(CC_ASAP)
    asap.criar_bm(bm_dados(a), [arquivo()])
    at = app("telas/asap_eng_bm_mensal.py")
    at.selectbox[0].select(a).run()
    next(b for b in at.button if b.label == "OK").click().run()
    _sem_erros(at)
    # sem BM selecionado não há botão de excluir; os botões do formulário são Salvar e Limpar
    assert not [b for b in at.button if (b.key or "").startswith("excluir-")]
    rotulos = [b.label for b in at.button]
    assert "Salvar" in rotulos and "Limpar" in rotulos


def _preencher(at: AppTest, valores: dict[str, str]):
    por_rotulo = {w.label: w for w in list(at.text_input) + list(at.text_area)}
    for rotulo, valor in valores.items():
        por_rotulo[rotulo].input(valor)


def test_cadastro_asap_pela_tela(app):
    at = app("telas/asap_eng_cadastro.py")
    coligada = next(w for w in at.text_input if w.label == "Coligada")
    assert (coligada.value, coligada.disabled) == ("ASAP", True)
    assert {w.label: len(w.options) for w in at.selectbox}["Fim de Medição (dia) *"] == 31
    _escolher(at, {"Início de Medição (dia) *": 20, "Fim de Medição (dia) *": 19})
    _preencher(at, {
        "Centro de Custo *": "DEV-TELA-1", "Cliente *": "Cliente DEV", "E-mail *": "dev@exemplo.invalid",
    })
    salvar = next(b for b in at.button if b.label == "Salvar")
    salvar.click().run()
    _sem_erros(at)
    [cc] = asap.listar_centros_custo()
    assert (cc.titulo, cc.inicio_medicao, cc.fim_medicao) == ("DEV-TELA-1", 20, 19)
    assert any("cadastrado com sucesso" in s.value for s in at.success)


def _escolher(at: AppTest, valores: dict):
    por_rotulo = {w.label: w for w in at.selectbox}
    for rotulo, valor in valores.items():
        por_rotulo[rotulo].select(valor)


def test_erro_de_validacao_mantem_digitacao_e_nao_mostra_sucesso(app):
    at = app("telas/superus_eng_cadastro.py")
    assert list(next(w for w in at.selectbox if w.label == "Coligada *").options) == [
        "SUPERUS ENGENHARIA", "ACPL", "SUPERUS HOLDING"
    ]
    assert {w.label: len(w.options) for w in at.selectbox}["Início de Medição (dia) *"] == 31
    _escolher(at, {"Início de Medição (dia) *": 5})
    _preencher(at, {"Centro de Custo *": "DEV-X"})
    next(b for b in at.button if b.label == "Salvar").click().run()
    _sem_erros(at)
    assert superus.listar_centros_custo() == []
    assert not at.success
    assert any("Não foi possível salvar" in e.value for e in at.error)
    assert {w.label: w.value for w in at.selectbox}["Início de Medição (dia) *"] == 5
    assert {w.label: w.value for w in at.text_input}["Centro de Custo *"] == "DEV-X"


def test_cadastro_superus_duplicado_pela_tela(app):
    superus.criar_centro_custo(CC_SUP)
    at = app("telas/superus_eng_cadastro.py")
    _escolher(at, {"Coligada *": "ACPL", "Início de Medição (dia) *": 1, "Fim de Medição (dia) *": 2})
    _preencher(at, {
        "Centro de Custo *": "dev-sup-100", "Nome do Gestor do Centro de custo *": "G",
        "Nome completo do Cliente *": "O",
    })
    next(b for b in at.button if b.label == "Salvar").click().run()
    assert len(superus.listar_centros_custo()) == 1
    assert any("já está cadastrado" in e.value for e in at.error)


def test_fluxo_escolha_e_confirmacao_de_cc_superus(app):
    cc_id = superus.criar_centro_custo(CC_SUP)
    at = app("telas/superus_eng_bm_mensal.py")
    assert [h.value for h in at.subheader] == ["Escolha seu Centro de Custos"]
    at.selectbox[0].select(cc_id).run()
    next(b for b in at.button if b.label == "OK").click().run()
    assert "Confirme seu Centro de Custo" in [h.value for h in at.subheader]
    assert any("Gestor de desenvolvimento" in m.value for m in at.markdown)
    next(b for b in at.button if b.label == "OK").click().run()
    _sem_erros(at)
    assert "Novo BM" in [h.value for h in at.subheader]


def test_faturamento_sem_selecao_nao_oferece_salvar(app):
    a = asap.criar_centro_custo(CC_ASAP)
    asap.criar_bm(bm_dados(a), [arquivo()])
    at = app("telas/asap_adm_faturamento.py")
    _sem_erros(at)
    assert not any(b.label == "Salvar" for b in at.button)
    assert any("não cria BMs" in i.value for i in at.info)


def test_configuracao_inicial_cria_admin_pela_tela_e_some_depois(ambiente):
    at = AppTest.from_file(APP, default_timeout=30).run()
    _preencher(
        at,
        {
            "Nome": "Administrador",
            "E-mail": "admin@empresa.test",
            "Senha (mínimo 8 caracteres)": "curta12",
            "Confirme a senha": "curta12",
        },
    )
    next(b for b in at.button if b.label == "Criar administrador").click().run()
    assert any("Corrija os campos" in e.value for e in at.error)

    _preencher(at, {"Senha (mínimo 8 caracteres)": "senha123", "Confirme a senha": "senha123"})
    next(b for b in at.button if b.label == "Criar administrador").click().run()
    _sem_erros(at)
    assert ("Controle de acesso", "controle-acesso") in _links(at, "sidebar")

    nova_sessao = AppTest.from_file(APP, default_timeout=30).run()
    assert not any(b.label == "Criar administrador" for b in nova_sessao.button)
    assert any(b.label == "Entrar" for b in nova_sessao.button)


def test_solicitacao_pela_tela_de_login_e_aprovacao_no_controle_de_acesso(ambiente):
    from sim.auth import PERFIL_CONTROLE_GERAL, autenticar

    st.cache_resource.clear()
    a = asap.criar_centro_custo(CC_ASAP)
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        admin = Usuario(
            email="admin@empresa.test",
            email_normalizado="admin@empresa.test",
            nome="Administrador",
            senha_hash="hash-nao-usado-no-teste",
            perfil=PERFIL_CONTROLE_GERAL,
            ativo=True,
            deve_trocar_senha=False,
        )
        session.add(admin)
        session.flush()
        admin_id = admin.id

    login = AppTest.from_file(APP, default_timeout=30).run()
    assert [t.label for t in login.tabs] == ["Entrar", "Solicitar acesso", "Esqueci a senha"]
    _preencher(
        login,
        {
            "Nome completo": "Pessoa da Obra",
            "Senha (mínimo 8 caracteres)": "senha123",
            "Confirme a senha": "senha123",
            "Centro de custo do contrato": "CC 1234 - Obra Alfa",
        },
    )
    # Há dois campos "E-mail" (Entrar e Solicitar); o segundo é o da solicitação.
    campo_email = lambda: [c for c in login.text_input if c.label == "E-mail"][1]  # noqa: E731
    campo_email().input("obra@dominio-errado.test")
    next(b for b in login.button if b.label == "Enviar solicitação").click().run()
    assert any("dominio-errado.test não está autorizado" in m.value for m in login.markdown)  # barrado na hora
    assert not login.success
    campo_email().input("obra@empresa.test")
    next(b for b in login.button if b.label == "Enviar solicitação").click().run()
    _sem_erros(login)
    assert any("Solicitação enviada" in s.value for s in login.success)

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = admin_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    assert any("aguardando aprovação" in w.value for w in at.warning)
    at.switch_page("telas/controle_acesso.py").run()
    _sem_erros(at)
    assert any("CC 1234 - Obra Alfa" in c.value for c in at.code)
    at.multiselect(key=next(m.key for m in at.multiselect if m.label == "Centros de custo a liberar")).select(
        ("ASAP", a)
    ).run()
    next(b for b in at.button if b.label == "Aprovar").click().run()
    _sem_erros(at)
    assert not [b for b in at.button if b.label == "Aprovar"]

    principal_login = autenticar("obra@empresa.test", "senha123")
    assert principal_login is not None


def test_administrador_geral_ve_telas_de_obra_e_controle_de_acesso(ambiente):
    from sim.auth import PERFIL_CONTROLE_GERAL

    st.cache_resource.clear()
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        usuario = Usuario(
            email="geral@empresa.test",
            email_normalizado="geral@empresa.test",
            nome="Administrador geral",
            senha_hash="hash-nao-usado-no-teste",
            perfil=PERFIL_CONTROLE_GERAL,
            ativo=True,
            deve_trocar_senha=False,
        )
        session.add(usuario)
        session.flush()
        usuario_id = usuario.id

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = usuario_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    _sem_erros(at)
    assert ("Controle de acesso", "controle-acesso") in _links(at, "sidebar")
    assert len(_links(at)) >= 3  # cartões das áreas ASAP, Superus e Administrativo
    for tela in ("telas/asap_eng_bm_mensal.py", "telas/controle_acesso.py"):
        at.switch_page(tela).run()
        _sem_erros(at)


def test_esqueci_a_senha_pela_tela(ambiente, monkeypatch):
    import re
    from email import message_from_bytes, policy

    from sim.auth import PERFIL_USUARIO, autenticar, hash_senha

    monkeypatch.setenv("SIM_EMAIL_MODO", "arquivo")
    st.cache_resource.clear()
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        session.add(
            Usuario(
                email="pessoa@empresa.test",
                email_normalizado="pessoa@empresa.test",
                nome="Pessoa",
                senha_hash=hash_senha("senha-antiga-123"),
                perfil=PERFIL_USUARIO,
                ativo=True,
                deve_trocar_senha=False,
            )
        )

    at = AppTest.from_file(APP, default_timeout=30).run()
    _preencher(at, {"E-mail da conta": "pessoa@empresa.test"})
    next(b for b in at.button if b.label == "Enviar código").click().run()
    _sem_erros(at)
    assert any("enviamos um código" in i.value for i in at.info)

    [eml] = (ambiente.data_dir / "emails").glob("*.eml")
    corpo = message_from_bytes(eml.read_bytes(), policy=policy.default).get_content()
    codigo = re.search(r"\b(\d{6})\b", corpo).group(1)
    _preencher(
        at,
        {
            "Código recebido": codigo,
            "Nova senha (mínimo 8 caracteres)": "senha-nova-123",
            "Confirme a nova senha": "senha-nova-123",
        },
    )
    next(b for b in at.button if b.label == "Redefinir senha").click().run()
    _sem_erros(at)
    assert any("Senha redefinida" in s.value for s in at.success)
    assert autenticar("pessoa@empresa.test", "senha-nova-123") is not None


def _abrir_como_usuario_de_obra(cc_id: int):
    from sim.auth import PERFIL_USUARIO
    from sim.models import AcessoCentroCusto, SuperusCentroCusto

    st.cache_resource.clear()
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        usuario = Usuario(
            email="obra@empresa.test",
            email_normalizado="obra@empresa.test",
            nome="Usuário de obra",
            senha_hash="hash-nao-usado-no-teste",
            perfil=PERFIL_USUARIO,
            ativo=True,
            deve_trocar_senha=False,
        )
        session.add(usuario)
        session.flush()
        empresa_id = session.get(SuperusCentroCusto, cc_id).empresa_id
        session.add(AcessoCentroCusto(usuario_id=usuario.id, empresa_id=empresa_id, superus_centro_custo_id=cc_id))
        usuario_id = usuario.id

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = usuario_id
    at.session_state["_sim_versao_sessao"] = 1
    return at.run()


def _confirmar_cc(at: AppTest, cc_id: int) -> None:
    at.selectbox[0].select(cc_id).run()
    next(b for b in at.button if b.label == "OK").click().run()
    next(b for b in at.button if b.label == "OK").click().run()


def test_usuario_de_obra_solicita_encerramento_pela_tela(ambiente):
    from sim.services import encerramento

    cc_id = superus.criar_centro_custo(CC_SUP)
    at = _abrir_como_usuario_de_obra(cc_id)
    _sem_erros(at)

    at.switch_page("telas/modulo_superus_eng.py").run()
    _sem_erros(at)
    paginas = [p for _, p in _links(at)]
    assert "superus-encerramento" in paginas and "superus-cadastro" not in paginas

    at.switch_page("telas/superus_eng_bm_mensal.py").run()
    _sem_erros(at)
    _confirmar_cc(at, cc_id)
    _sem_erros(at)
    assert "Novo BM" in [h.value for h in at.subheader]
    assert ("Fim Mês (Encerramento)", "superus-encerramento") in _links(at)

    at.switch_page("telas/superus_eng_bm_semanal.py").run()
    _sem_erros(at)

    at.switch_page("telas/superus_eng_encerramento.py").run()
    _sem_erros(at)
    assert not [s for s in at.subheader if s.value == "Solicitações aguardando aprovação"]  # não decide
    at.selectbox(key=next(s.key for s in at.selectbox if s.label == "Centro de custo")).select(cc_id).run()
    next(b for b in at.button if b.label == "Enviar solicitação").click().run()
    assert any("Justificativa" in e.value for e in at.error)  # obrigatória
    next(t for t in at.text_area if t.label.startswith("Justificativa")).input("Contrato encerrado.")
    next(b for b in at.button if b.label == "Enviar solicitação").click().run()
    _sem_erros(at)
    assert any("Solicitação enviada" in s.value for s in at.success)
    assert any("aguardando aprovação" in i.value for i in at.info)
    with session_scope() as session:
        from sim.models import EncerramentoCentroCusto

        pedido = session.query(EncerramentoCentroCusto).one()
        assert (pedido.status, pedido.justificativa) == (encerramento.PENDENTE, "Contrato encerrado.")


def test_controlador_aprova_encerramento_e_bm_novo_some(app):
    from sim.auth import PERFIL_USUARIO, Principal, usando_principal
    from sim.services import encerramento

    cc_id = superus.criar_centro_custo(CC_SUP)
    at = app()  # cria o controlador (id 1) usado como decisor
    with session_scope() as session:
        obra = Usuario(email="o@empresa.test", email_normalizado="o@empresa.test", nome="Obra",
                       senha_hash="x", perfil=PERFIL_USUARIO, ativo=True, deve_trocar_senha=False)
        session.add(obra)
        session.flush()
        obra_id = obra.id
    with usando_principal(Principal(obra_id, "o@empresa.test", "Obra", PERFIL_USUARIO, 1, (("SUPERUS", cc_id),))):
        encerramento.solicitar_encerramento("SUPERUS", cc_id, "Obra concluída")

    at.run()
    assert any("encerramento de centro de custo aguardando" in w.value for w in at.warning)
    at.switch_page("telas/superus_eng_encerramento.py").run()
    _sem_erros(at)
    assert any("Obra concluída" in c.value for c in at.code)
    next(b for b in at.button if b.label == "Aprovar encerramento").click().run()
    _sem_erros(at)
    assert not superus.obter_centro_custo(cc_id).ativo

    at.switch_page("telas/superus_eng_bm_mensal.py").run()
    _confirmar_cc(at, cc_id)
    _sem_erros(at)
    assert any("encerrado" in w.value for w in at.warning)
    assert not [b for b in at.button if b.label == "Salvar"]

    at.switch_page("telas/superus_eng_cadastro.py").run()
    _sem_erros(at)  # tabela com a coluna Ativo editável (st.data_editor) abre sem erro


def test_controlador_ve_atalho_fim_mes(app):
    cc_id = superus.criar_centro_custo(CC_SUP)
    at = app("telas/superus_eng_bm_mensal.py")
    _confirmar_cc(at, cc_id)
    _sem_erros(at)
    assert ("Fim Mês (Encerramento)", "superus-encerramento") in _links(at)


def test_criar_usuario_de_obra_escolhendo_coligada_e_centros(ambiente):
    from sim.auth import PERFIL_CONTROLE_GERAL, autenticar, carregar_principal

    st.cache_resource.clear()
    asap_id = asap.criar_centro_custo(CC_ASAP)
    sup_a = superus.criar_centro_custo({**CC_SUP, "titulo": "SUP-A"})
    superus.criar_centro_custo({**CC_SUP, "titulo": "SUP-B"})
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        admin = Usuario(email="admin@empresa.test", email_normalizado="admin@empresa.test", nome="Admin",
                        senha_hash="x", perfil=PERFIL_CONTROLE_GERAL, ativo=True, deve_trocar_senha=False)
        session.add(admin)
        session.flush()
        admin_id = admin.id

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = admin_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    at.switch_page("telas/controle_acesso.py").run()
    _sem_erros(at)
    campo = lambda rotulo: next(w for w in at.text_input if w.label == rotulo and "novo-usuario" in w.key)  # noqa: E731
    campo("Nome").input("Pessoa da Obra")
    campo("E-mail").input("obra@empresa.test")
    assert not [m for m in at.multiselect if m.label == "Centros de custo com acesso"]  # só depois da coligada
    next(s for s in at.selectbox if s.label == "Coligada").select("SUPERUS").run()
    centros = next(m for m in at.multiselect if m.label == "Centros de custo com acesso")
    assert list(centros.options) == ["SUP-A · SUPERUS ENGENHARIA", "SUP-B · SUPERUS ENGENHARIA"]  # só SUPERUS
    next(b for b in at.button if b.label == "Criar conta").click().run()
    assert any("centro de custo" in m.value for m in at.markdown)  # sem centro: recusado

    next(m for m in at.multiselect if m.label == "Centros de custo com acesso").select(sup_a).run()
    next(b for b in at.button if b.label == "Criar conta").click().run()
    _sem_erros(at)
    assert any("Conta criada" in s.value for s in at.success)
    [senha] = [c.value for c in at.code if len(c.value) > 20]
    assert campo("Nome").value == ""  # formulário volta vazio

    principal = carregar_principal(*autenticar("obra@empresa.test", senha))
    assert principal.escopos == (("SUPERUS", sup_a),)
    assert ("ASAP", asap_id) not in principal.escopos


def test_propria_conta_no_controle_de_acesso_e_erro_com_motivo(ambiente):
    from sim.auth import PERFIL_CONTROLE_GERAL
    from sim.errors import ValidationError

    st.cache_resource.clear()
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        admin = Usuario(email="geral@empresa.test", email_normalizado="geral@empresa.test", nome="Geral",
                        senha_hash="x", perfil=PERFIL_CONTROLE_GERAL, ativo=True, deve_trocar_senha=False)
        session.add(admin)
        session.flush()
        admin_id = admin.id

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = admin_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    at.switch_page("telas/controle_acesso.py").run()
    _sem_erros(at)
    botoes = {b.label: b for b in at.button}
    assert botoes["Redefinir senha"].disabled and botoes["Desativar conta"].disabled
    assert any("Trocar senha" in c.value for c in at.caption)
    assert any(b.label == "Trocar senha" for b in at.sidebar.button)

    # Erro de validação mostra o motivo, não só "Corrija os campos indicados".
    assert ValidationError({"usuario": "Use a troca de senha da sua própria conta."}).descricao() == (
        "Use a troca de senha da sua própria conta."
    )
    varios = ValidationError({"a": "Motivo A.", "b": "Motivo B."}).descricao()
    assert "Motivo A." in varios and "Motivo B." in varios


def test_trocar_a_propria_senha_pela_barra_lateral(ambiente):
    from sim.auth import PERFIL_CONTROLE_GERAL, autenticar, hash_senha

    st.cache_resource.clear()
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        usuario = Usuario(email="g@empresa.test", email_normalizado="g@empresa.test", nome="G",
                          senha_hash=hash_senha("senha-antiga-1"), perfil=PERFIL_CONTROLE_GERAL, ativo=True,
                          deve_trocar_senha=False)
        session.add(usuario)
        session.flush()
        usuario_id = usuario.id

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = usuario_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    next(b for b in at.sidebar.button if b.label == "Trocar senha").click().run()

    def enviar(atual, nova, confirmacao):
        campos = {t.label: t for t in at.text_input}
        campos["Senha atual"].input(atual)
        campos["Nova senha (mínimo 8 caracteres)"].input(nova)
        campos["Confirme a nova senha"].input(confirmacao)
        next(b for b in at.button if b.label == "Salvar nova senha").click().run()

    enviar("senha-antiga-1", "nova-senha-1", "outra-senha-1")
    _sem_erros(at)
    assert at.error and "Corrija os campos" not in at.error[0].value  # mostra o motivo
    enviar("senha-antiga-1", "nova-senha-1", "nova-senha-1")
    _sem_erros(at)
    assert not [t for t in at.text_input if t.label == "Senha atual"]  # diálogo fechou
    assert autenticar("g@empresa.test", "nova-senha-1") is not None
    assert at.session_state["_sim_versao_sessao"] == 2  # continua logado nesta sessão


@pytest.mark.parametrize("perfil", ["usuario"])
def test_troca_de_senha_voluntaria_so_para_administradores(ambiente, perfil):
    from sim.auth import (
        AuthorizationError,
        MSG_TROCA_SO_ADMIN,
        autenticar,
        carregar_principal,
        hash_senha,
        trocar_senha,
        usando_principal,
    )

    st.cache_resource.clear()
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        usuario = Usuario(email="obra@empresa.test", email_normalizado="obra@empresa.test", nome="Obra",
                          senha_hash=hash_senha("senha-antiga-1"), perfil=perfil, ativo=True,
                          deve_trocar_senha=False)
        session.add(usuario)
        session.flush()
        usuario_id = usuario.id

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = usuario_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    _sem_erros(at)
    assert not [b for b in at.sidebar.button if b.label == "Trocar senha"]
    assert any(b.label == "Sair" for b in at.sidebar.button)

    principal = carregar_principal(*autenticar("obra@empresa.test", "senha-antiga-1"))
    with usando_principal(principal):
        with pytest.raises(AuthorizationError) as erro:  # o serviço também recusa
            trocar_senha(usuario_id, "senha-antiga-1", "nova-senha-1", "nova-senha-1")
    assert erro.value.message == MSG_TROCA_SO_ADMIN


def test_senha_temporaria_ainda_e_trocada_por_usuario_de_obra(ambiente):
    from sim.auth import autenticar, carregar_principal, hash_senha, trocar_senha, usando_principal

    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        usuario = Usuario(email="obra@empresa.test", email_normalizado="obra@empresa.test", nome="Obra",
                          senha_hash=hash_senha("temporaria-123"), perfil="usuario", ativo=True,
                          deve_trocar_senha=True)
        session.add(usuario)
        session.flush()
        usuario_id = usuario.id
    principal = carregar_principal(*autenticar("obra@empresa.test", "temporaria-123"))
    with usando_principal(principal):
        trocar_senha(usuario_id, "temporaria-123", "definitiva-123", "definitiva-123")
    assert autenticar("obra@empresa.test", "definitiva-123") is not None


def test_controlador_geral_e_administrador_e_acessa_tudo(app):
    """Decisão de 2026-10-27: controlador geral vê todas as obras e também administra acessos."""
    at = app("telas/inicio.py")
    links = _links(at, "sidebar")
    assert ("Controle de acesso", "controle-acesso") in links
    assert any(b.label == "Trocar senha" for b in at.sidebar.button)
    at.switch_page("telas/controle_acesso.py").run()
    _sem_erros(at)
    assert "Controle de acesso" in [t.value for t in at.title]


def test_auditoria_mostra_quem_realizou_cada_acao(ambiente):
    from sim import access_admin
    from sim.auth import PERFIL_CONTROLE_GERAL, Principal, usando_principal

    st.cache_resource.clear()
    with session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        admin = Usuario(email="geral@empresa.test", email_normalizado="geral@empresa.test", nome="Pessoa Geral",
                        senha_hash="x", perfil=PERFIL_CONTROLE_GERAL, ativo=True, deve_trocar_senha=False)
        session.add(admin)
        session.flush()
        admin_id = admin.id
    with usando_principal(Principal(admin_id, "geral@empresa.test", "Pessoa Geral", PERFIL_CONTROLE_GERAL, 1, ())):
        access_admin.adicionar_dominio("outra.test")
        access_admin.criar_usuario("novo@empresa.test", "Pessoa Nova", "planejador")

    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["_sim_usuario_id"] = admin_id
    at.session_state["_sim_versao_sessao"] = 1
    at.run()
    at.switch_page("telas/controle_acesso.py").run()
    _sem_erros(at)
    tabela = at.dataframe[-1].value
    assert list(tabela.columns[:4]) == ["Data", "Realizado por", "Ação", "Usuário afetado"]
    assert set(tabela["Realizado por"]) == {"Pessoa Geral · geral@empresa.test"}
    assert "Pessoa Nova · novo@empresa.test" in set(tabela["Usuário afetado"])


def test_erro_some_ao_alterar_um_campo_e_volta_na_nova_tentativa(app):
    at = app("telas/asap_eng_cadastro.py")
    salvar = next(b for b in at.button if b.label == "Salvar")
    salvar.click().run()
    assert any("Corrija os campos" in e.value for e in at.error)  # tentativa sem os obrigatórios

    _preencher(at, {"Cliente *": "Cliente DEV"})  # o usuário mexe num campo, sem salvar
    at.run()
    assert not any("Corrija os campos" in e.value for e in at.error)

    next(b for b in at.button if b.label == "Salvar").click().run()  # nova tentativa: confere de novo
    assert any("Corrija os campos" in e.value for e in at.error)
    assert not asap.listar_centros_custo()
