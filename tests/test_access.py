from __future__ import annotations

import pytest
from sqlalchemy import select

from sim import access_admin, database
from sim import auth as auth_module
from sim.auth import (
    PERFIL_CONTROLE_GERAL,
    PERFIL_CONTROLE,
    PERFIL_USUARIO,
    Principal,
    autenticar,
    carregar_principal,
    hash_senha,
    usando_principal,
)
from sim.errors import AuthorizationError, ValidationError
from sim.models import DominioPermitido, Usuario
from sim.services import asap, common, superus
from tests.conftest import arquivo
from tests.test_asap import CC as CC_ASAP, bm_dados
from tests.test_superus import CC as CC_SUP, mensal


def _usuario(email: str, perfil: str, senha: str = "Senha-forte-de-teste-123") -> Usuario:
    return Usuario(
        email=email,
        email_normalizado=email.casefold(),
        nome="Usuário de teste",
        senha_hash=hash_senha(senha),
        perfil=perfil,
        ativo=True,
        deve_trocar_senha=False,
    )


def test_escopo_asap_filtra_listas_e_bloqueia_registros_e_anexos(ambiente):
    cc_autorizado = asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-ALFA"})
    cc_restrito = asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-BETA"})
    bm_autorizado = asap.criar_bm(bm_dados(cc_autorizado), [arquivo("alfa.pdf")])
    bm_restrito = asap.criar_bm(bm_dados(cc_restrito), [arquivo("beta.pdf")])
    anexo_restrito = asap.obter_bm(bm_restrito).anexos[0].id

    usuario = Principal(
        100,
        "alfa@empresa.test",
        "Obra Alfa",
        PERFIL_USUARIO,
        1,
        (("ASAP", cc_autorizado),),
    )
    with usando_principal(usuario):
        assert [c.id for c in asap.listar_centros_custo()] == [cc_autorizado]
        assert [b.id for b in asap.listar_bms()] == [bm_autorizado]
        assert asap.obter_bm(bm_autorizado).id == bm_autorizado
        with pytest.raises(AuthorizationError):
            asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-NAO-AUTORIZADA"})
        with pytest.raises(AuthorizationError):
            access_admin.listar_dominios()
        with pytest.raises(AuthorizationError):
            asap.obter_bm(bm_restrito)
        with pytest.raises(AuthorizationError):
            asap.listar_bms(centro_custo_id=cc_restrito)
        with pytest.raises(AuthorizationError):
            asap.criar_bm(bm_dados(cc_restrito), [arquivo()])
        with pytest.raises(AuthorizationError):
            asap.excluir_bm(bm_restrito)
        with pytest.raises(AuthorizationError):
            common.ler_anexo(anexo_restrito)


def test_usuario_com_multiplos_centros_superus_nao_ve_terceiro(ambiente):
    cc_um = superus.criar_centro_custo({**CC_SUP, "titulo": "SUP-UM"})
    cc_dois = superus.criar_centro_custo({**CC_SUP, "titulo": "SUP-DOIS"})
    cc_outro = superus.criar_centro_custo({**CC_SUP, "titulo": "SUP-OUTRO"})
    bm_um = superus.criar_bm_mensal(cc_um, mensal(), [arquivo("um.pdf")])
    bm_dois = superus.criar_bm_mensal(cc_dois, mensal(titulo="BM-DOIS"), [arquivo("dois.pdf")])
    bm_outro = superus.criar_bm_mensal(cc_outro, mensal(titulo="BM-OUTRO"), [arquivo("outro.pdf")])
    usuario = Principal(
        101,
        "gerente@empresa.test",
        "Gerente",
        PERFIL_USUARIO,
        1,
        (("SUPERUS", cc_um), ("SUPERUS", cc_dois)),
    )

    with usando_principal(usuario):
        assert {c.id for c in superus.listar_centros_custo()} == {cc_um, cc_dois}
        assert {b.id for b in superus.listar_bms_mensais()} == {bm_um, bm_dois}
        with pytest.raises(AuthorizationError):
            superus.atualizar_faturamento(
                bm_outro,
                status="Faturado Total",
                valor_liberado="10",
                valor_emitido="10",
                mes_referencia="Janeiro",
                frs="1",
                po="X",
                novos_anexos=[],
            )


def test_controlador_geral_tem_acesso_global_e_cria_centros(ambiente):
    cc_id = asap.criar_centro_custo({**CC_ASAP, "titulo": "GLOBAL-CC"})
    assert any(c.id == cc_id for c in asap.listar_centros_custo())
    assert len(asap.listar_centros_custo()) == 1


def test_login_exige_conta_ativa_e_dominio_autorizado(ambiente):
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        usuario = _usuario("pessoa@empresa.test", PERFIL_USUARIO)
        session.add(usuario)

    assert autenticar("PESSOA@EMPRESA.TEST", "Senha-forte-de-teste-123") is not None
    assert autenticar("pessoa@empresa.test", "senha errada") is None

    with database.session_scope() as session:
        dominio = session.scalar(select(DominioPermitido).where(DominioPermitido.dominio == "empresa.test"))
        dominio.ativo = False
    assert autenticar("pessoa@empresa.test", "Senha-forte-de-teste-123") is None


def test_bloqueio_apos_cinco_senhas_incorretas(ambiente, monkeypatch):
    monkeypatch.setattr(auth_module, "_PBKDF2_ITERATIONS", 1_000)
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        session.add(_usuario("pessoa@empresa.test", PERFIL_USUARIO))

    for _ in range(5):
        assert autenticar("pessoa@empresa.test", "senha errada") is None
    assert autenticar("pessoa@empresa.test", "Senha-forte-de-teste-123") is None
    with database.session_scope() as session:
        usuario = session.scalar(select(Usuario).where(Usuario.email_normalizado == "pessoa@empresa.test"))
        assert usuario.bloqueado_ate is not None


def test_admin_provisiona_usuario_concede_escopo_e_audita(ambiente):
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        administrador = _usuario("admin@empresa.test", PERFIL_CONTROLE_GERAL)
        session.add(administrador)
        session.flush()
        admin_id = administrador.id

    cc_id = asap.criar_centro_custo({**CC_ASAP, "titulo": "CC-GERENCIADO"})
    admin = Principal(admin_id, "admin@empresa.test", "Admin", PERFIL_CONTROLE_GERAL, 1, ())
    with usando_principal(admin):
        with pytest.raises(ValidationError) as erro:  # usuário de obra precisa de centro de custo
            access_admin.criar_usuario("obra@empresa.test", "Obra Alfa")
        assert "centro_custo" in erro.value.errors
        usuario_id, senha_temporaria = access_admin.criar_usuario(
            "obra@empresa.test", "Obra Alfa", centros=[("ASAP", cc_id)]
        )

    with database.session_scope() as session:
        usuario = session.get(Usuario, usuario_id)
        assert usuario.deve_trocar_senha
    login = autenticar("obra@empresa.test", senha_temporaria)
    assert login is not None
    principal = carregar_principal(*login)
    assert principal is not None
    assert principal.escopos == (("ASAP", cc_id),)
    with database.session_scope() as session:
        assert len(list(session.scalars(select(access_admin.AuditoriaAcesso)))) == 2


def test_conta_sem_grupo_de_dominio_nao_pode_ser_criada(ambiente):
    with database.session_scope() as session:
        admin = _usuario("admin@empresa.test", PERFIL_CONTROLE_GERAL)
        session.add(admin)
        session.flush()
        admin_id = admin.id
    administrador = Principal(admin_id, "admin@empresa.test", "Admin", PERFIL_CONTROLE_GERAL, 1, ())

    with usando_principal(administrador):
        with pytest.raises(ValidationError):
            access_admin.criar_usuario("pessoa@naoautorizado.test", "Pessoa", PERFIL_CONTROLE)


def test_servicos_fecham_sem_contexto_autenticado(ambiente):
    with pytest.raises(AuthorizationError):
        with usando_principal(None):
            asap.listar_centros_custo()


def test_primeiro_administrador_so_pode_ser_criado_com_banco_vazio(ambiente):
    with pytest.raises(ValidationError):
        auth_module.criar_primeiro_administrador("admin@empresa.test", "Admin", "1234567", "1234567")
    usuario_id, versao = auth_module.criar_primeiro_administrador(
        "Admin@Empresa.test", "Admin", "12345678", "12345678"
    )
    principal = carregar_principal(usuario_id, versao)
    assert principal is not None and principal.administrador_acessos
    assert autenticar("admin@empresa.test", "12345678") is not None
    with pytest.raises(AuthorizationError):
        auth_module.criar_primeiro_administrador("outro@empresa.test", "Outro", "12345678", "12345678")


def test_administrador_geral_ve_todas_as_obras_e_administra_acessos(ambiente):
    from sim.auth import PERFIL_CONTROLE_GERAL

    cc_id = asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-GERAL"})
    with database.session_scope() as session:
        session.add(DominioPermitido(dominio="empresa.test", ativo=True))
        admin = _usuario("geral@empresa.test", PERFIL_CONTROLE_GERAL)
        session.add(admin)
        session.flush()
        admin_id = admin.id

    assert auth_module.existe_administrador_inicializado()
    geral = carregar_principal(*autenticar("geral@empresa.test", "Senha-forte-de-teste-123"))
    assert geral.controle_geral and geral.controlador and geral.administrador_acessos
    with usando_principal(geral):
        assert [c.id for c in asap.listar_centros_custo()] == [cc_id]
        asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-NOVA"})
        usuario_id, _ = access_admin.criar_usuario("obra@empresa.test", "Obra", centros=[("ASAP", cc_id)])
        # Única conta Controle Geral: não pode ser rebaixada nem desativada.
        with pytest.raises(ValidationError):
            access_admin.alterar_perfil(admin_id, PERFIL_USUARIO)
        access_admin.alterar_perfil(usuario_id, PERFIL_CONTROLE_GERAL)
        with pytest.raises(ValidationError):
            access_admin.definir_usuario_ativo(admin_id, False)
