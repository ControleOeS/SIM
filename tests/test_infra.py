"""Separação entre empresas, integridade, persistência, erros de gravação e anexos."""
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError

from sim import database
from sim.bootstrap import versao_atual, versao_esperada
from sim.errors import PersistenceError, ValidationError
from sim.models import Anexo, AsapBM, Empresa, SuperusBMMensal
from sim.services import asap, common, superus
from tests.conftest import arquivo
from tests.test_asap import CC as CC_ASAP, bm_dados
from tests.test_superus import CC as CC_SUP, mensal


def test_migracoes_criam_esquema_e_empresas(ambiente):
    assert versao_atual() == versao_esperada(ambiente.database_url)
    tabelas = set(inspect(database.get_engine()).get_table_names())
    assert {
        "empresas", "asap_centros_custo", "asap_bms", "superus_centros_custo",
        "superus_bms_mensais", "superus_bms_semanais", "anexos", "usuarios",
        "dominios_permitidos", "acessos_centros_custo", "auditoria_acessos", "alembic_version",
    } <= tabelas
    with database.session_scope() as s:
        assert sorted(s.scalars(select(Empresa.codigo))) == ["ASAP", "SUPERUS"]


# 4. Separação ASAP x SUPERUS
def test_separacao_entre_empresas(ambiente):
    cc_a = asap.criar_centro_custo({**CC_ASAP, "titulo": "MESMO-CODIGO"})
    cc_s = superus.criar_centro_custo({**CC_SUP, "titulo": "MESMO-CODIGO"})  # listas diferentes: permitido
    asap.criar_bm(bm_dados(cc_a), [arquivo()])

    assert [c.titulo for c in asap.listar_centros_custo()] == ["MESMO-CODIGO"]
    assert [c.titulo for c in superus.listar_centros_custo()] == ["MESMO-CODIGO"]
    assert superus.listar_bms_mensais() == []
    assert len(asap.listar_bms()) == 1
    with database.session_scope() as s:
        empresas = {e.id: e.codigo for e in s.scalars(select(Empresa))}
    assert empresas[asap.listar_centros_custo()[0].empresa_id] == "ASAP"
    assert empresas[superus.obter_centro_custo(cc_s).empresa_id] == "SUPERUS"

    # Um ID de CC da SUPERUS não serve para um BM da ASAP (e vice-versa)
    superus.criar_centro_custo({**CC_SUP, "titulo": "SO-SUPERUS"})
    with pytest.raises(ValidationError):
        asap.criar_bm(bm_dados(cc_a + 10), [arquivo()])


# 8. Integridade no próprio banco (chaves estrangeiras ativas)
def test_banco_recusa_bm_orfao(ambiente):
    with pytest.raises(IntegrityError):
        with database.session_scope() as s:
            s.add(
                AsapBM(
                    centro_custo_id=999, titulo="x", ano="2026", mes_referencia="Janeiro",
                    status="s", valor_bm=1, valor_aprovado=0,
                )
            )


def test_banco_recusa_anexo_sem_dono(ambiente):
    with pytest.raises(IntegrityError):
        with database.session_scope() as s:
            s.add(Anexo(nome_original="a", caminho_relativo="x/a", tamanho_bytes=1, sha256="0" * 64))


# 9. Persistência após reiniciar
def test_dados_persistem_apos_reiniciar(ambiente):
    cc_id = superus.criar_centro_custo(CC_SUP)
    bm_id = superus.criar_bm_mensal(cc_id, mensal(), [arquivo(conteudo=b"persistente")])
    database.dispose_engine()  # simula fechar o Streamlit

    assert Path(ambiente.database_url.removeprefix("sqlite:///")).is_file()
    database.init_engine(ambiente)  # simula reabrir
    bm = superus.obter_bm_mensal(bm_id)
    assert bm.titulo == "BM-SUP-DEV"
    _, conteudo = common.ler_anexo(bm.anexos[0].id)
    assert conteudo == b"persistente"


# 10. Tratamento de erros de gravação
def test_falha_no_commit_vira_mensagem_e_nao_deixa_lixo(ambiente, monkeypatch):
    cc_id = superus.criar_centro_custo(CC_SUP)
    from sqlalchemy.orm import Session

    original = Session.commit

    def falhar(self):
        raise OperationalError("COMMIT", {}, Exception("disco cheio (simulado)"))

    monkeypatch.setattr(Session, "commit", falhar)
    with pytest.raises(PersistenceError) as e:
        superus.criar_bm_mensal(cc_id, mensal(), [arquivo()])
    monkeypatch.setattr(Session, "commit", original)

    assert "Nada foi salvo" in e.value.message
    assert "disco cheio" not in e.value.message  # detalhe técnico não vai para o usuário
    assert e.value.ref in e.value.message
    assert superus.listar_bms_mensais() == []
    anexos_dir = ambiente.anexos_dir
    assert not any(p.is_file() for p in anexos_dir.rglob("*"))  # arquivo gravado foi removido


def test_erro_de_validacao_nao_e_persistido(ambiente):
    with pytest.raises(ValidationError):
        superus.criar_bm_mensal(1, mensal(valor_bm="abc"), [arquivo()])
    with database.session_scope() as s:
        assert s.scalars(select(SuperusBMMensal)).all() == []


# 12. Upload e recuperação de anexos
def test_anexos_upload_download_e_remocao(ambiente):
    cc_id = asap.criar_centro_custo(CC_ASAP)
    bm_id = asap.criar_bm(bm_dados(cc_id), [arquivo("../../BM Março.xlsx", b"planilha"), arquivo("b.pdf", b"pdf")])
    bm = asap.obter_bm(bm_id)
    assert sorted(a.nome_original for a in bm.anexos) == ["../../BM Março.xlsx", "b.pdf"]

    for a in bm.anexos:
        assert a.caminho_relativo.startswith(f"asap/bm/{bm_id}/")
        assert ".." not in a.caminho_relativo
        assert (ambiente.anexos_dir / a.caminho_relativo).is_file()
    meta, conteudo = common.ler_anexo(next(a.id for a in bm.anexos if a.nome_original == "b.pdf"))
    assert conteudo == b"pdf" and meta.tamanho_bytes == 3 and len(meta.sha256) == 64

    # remove um anexo na edição
    remover = next(a for a in bm.anexos if a.nome_original == "b.pdf")
    asap.atualizar_bm(bm_id, bm_dados(cc_id), [], remover_anexo_ids=[remover.id])
    assert [a.nome_original for a in asap.obter_bm(bm_id).anexos] == ["../../BM Março.xlsx"]
    assert not (ambiente.anexos_dir / remover.caminho_relativo).exists()

    # excluir o BM remove os arquivos
    caminho = asap.obter_bm(bm_id).anexos[0].caminho_relativo
    asap.excluir_bm(bm_id)
    assert not (ambiente.anexos_dir / caminho).exists()
    with database.session_scope() as s:
        assert s.scalars(select(Anexo)).all() == []


def test_anexo_vazio_recusado(ambiente):
    cc_id = asap.criar_centro_custo(CC_ASAP)
    with pytest.raises(ValidationError):
        asap.criar_bm(bm_dados(cc_id), [arquivo(conteudo=b"")])
