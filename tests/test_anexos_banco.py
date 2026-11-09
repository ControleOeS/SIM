"""Anexos no banco (SIM_ANEXOS_BACKEND=banco), usado na hospedagem sem disco persistente.

O conteúdo entra na mesma transação do BM: nada fica órfão se a gravação falhar, e excluir o BM ou
remover o anexo apaga o conteúdo junto.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from sim import database
from sim.errors import ValidationError
from sim.models import AnexoConteudo
from sim.services import asap, common
from sim.storage import BancoStorage
from tests.conftest import arquivo
from tests.test_asap import CC as CC_ASAP, bm_dados


@pytest.fixture
def banco(ambiente, monkeypatch):
    monkeypatch.setenv("SIM_ANEXOS_BACKEND", "banco")
    assert isinstance(common.get_storage(), BancoStorage)
    return ambiente


def _conteudos() -> int:
    with database.session_scope() as s:
        return s.scalar(select(func.count()).select_from(AnexoConteudo))


def test_grava_le_e_remove_no_banco(banco):
    cc = asap.criar_centro_custo(CC_ASAP)
    bm_id = asap.criar_bm(bm_dados(cc), [arquivo("a.pdf", b"PDF-A"), arquivo("b.pdf", b"PDF-B")])
    assert _conteudos() == 2
    assert not any(banco.anexos_dir.rglob("*.pdf"))  # nada no disco

    bm = asap.obter_bm(bm_id)
    por_nome = {a.nome_original: a for a in bm.anexos}
    assert common.ler_anexo(por_nome["a.pdf"].id)[1] == b"PDF-A"
    assert common.carregador_anexo(por_nome["b.pdf"].id)() == b"PDF-B"

    asap.atualizar_bm(bm_id, bm_dados(cc), [arquivo("c.pdf", b"PDF-C")], [por_nome["a.pdf"].id])
    assert _conteudos() == 2  # saiu a.pdf, entrou c.pdf
    asap.excluir_bm(bm_id)
    assert _conteudos() == 0


def test_falha_na_gravacao_nao_deixa_conteudo_orfao(banco):
    cc = asap.criar_centro_custo(CC_ASAP)
    with pytest.raises(ValidationError):
        asap.criar_bm({**bm_dados(cc), "valor_bm": "abc"}, [arquivo()])
    bm_id = asap.criar_bm(bm_dados(cc), [arquivo()])
    with pytest.raises(ValidationError):  # remover o único anexo é recusado; o novo também não entra
        asap.atualizar_bm(bm_id, {**bm_dados(cc), "valor_bm": "abc"}, [arquivo("novo.pdf")])
    assert _conteudos() == 1


def test_backend_invalido_e_recusado(ambiente, monkeypatch):
    monkeypatch.setenv("SIM_ANEXOS_BACKEND", "nuvem")
    with pytest.raises(ValueError):
        common.get_storage()
