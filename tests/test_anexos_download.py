"""Download de anexos sob demanda: arquivo idêntico, leitura só no clique e permissão conferida na leitura."""
from __future__ import annotations

import hashlib
import os
import threading

import pytest

from sim.auth import PERFIL_USUARIO, Principal, usando_principal
from sim.errors import AuthorizationError
from sim.services import asap, common
from sim.storage import LocalFileStorage
from tests.conftest import arquivo
from tests.test_asap import CC as CC_ASAP, bm_dados

# PDF mínimo com bytes binários (inclui valores acima de 0x7F) para provar que nada é alterado.
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n" + os.urandom(256 * 1024) + b"\n%%EOF\n"


def _em_outra_thread(funcao):
    """Executa como o Streamlit faz com o download: em outra thread, sem o contexto da sessão."""
    resultado: dict = {}

    def alvo():
        try:
            resultado["valor"] = funcao()
        except Exception as exc:  # noqa: BLE001 - devolvido para o teste conferir
            resultado["erro"] = exc

    t = threading.Thread(target=alvo)
    t.start()
    t.join(timeout=30)
    return resultado


def _bm_com_pdf(titulo: str = "OBRA-PDF") -> tuple[int, int]:
    cc_id = asap.criar_centro_custo({**CC_ASAP, "titulo": titulo})
    bm_id = asap.criar_bm(bm_dados(cc_id), [arquivo("Medição março.pdf", PDF)])
    return cc_id, asap.obter_bm(bm_id).anexos[0].id


def test_pdf_enviado_e_baixado_e_identico(ambiente):
    _, anexo_id = _bm_com_pdf()
    meta = common.verificar_anexo(anexo_id)
    assert meta.nome_original == "Medição março.pdf"
    assert meta.tamanho_bytes == len(PDF)
    assert meta.sha256 == hashlib.sha256(PDF).hexdigest()

    resultado = _em_outra_thread(common.carregador_anexo(anexo_id))
    assert "erro" not in resultado, resultado.get("erro")
    assert resultado["valor"] == PDF


def test_tela_so_le_o_arquivo_no_clique(ambiente, monkeypatch):
    _, anexo_id = _bm_com_pdf()
    leituras = []
    original = LocalFileStorage.ler
    monkeypatch.setattr(LocalFileStorage, "ler", lambda self, c: leituras.append(c) or original(self, c))

    common.verificar_anexo(anexo_id)
    carregar = common.carregador_anexo(anexo_id)
    assert leituras == []  # montar a tela não lê o conteúdo
    assert carregar() == PDF
    assert len(leituras) == 1


def test_download_confere_permissao_na_hora_da_leitura(ambiente):
    cc_alfa, _ = _bm_com_pdf("OBRA-ALFA")
    _, anexo_beta = _bm_com_pdf("OBRA-BETA")
    usuario_alfa = Principal(100, "alfa@empresa.test", "Alfa", PERFIL_USUARIO, 1, (("ASAP", cc_alfa),))

    with usando_principal(usuario_alfa):
        with pytest.raises(AuthorizationError):
            common.verificar_anexo(anexo_beta)
        carregar_beta = common.carregador_anexo(anexo_beta)
    resultado = _em_outra_thread(carregar_beta)
    assert isinstance(resultado.get("erro"), AuthorizationError)


def test_carregador_exige_usuario_autenticado(ambiente):
    _, anexo_id = _bm_com_pdf()
    with usando_principal(None):
        with pytest.raises(AuthorizationError):
            common.carregador_anexo(anexo_id)


def _tela_anexos(bm_id: int):
    from sim.auth import PERFIL_CONTROLE, Principal, usando_principal
    from sim.services import asap
    from sim.ui import common as ui

    with usando_principal(Principal(1, "t@empresa.test", "T", PERFIL_CONTROLE, 1, ())):
        ui.anexos_download("teste", asap.obter_bm(bm_id).anexos, ctx=bm_id)


def test_tela_mostra_botao_baixar_sem_ler_arquivo(ambiente, monkeypatch):
    from streamlit.testing.v1 import AppTest

    cc_id = asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-TELA"})
    bm_id = asap.criar_bm(bm_dados(cc_id), [arquivo("a.pdf", PDF), arquivo("b.pdf", b"%PDF-curto")])
    monkeypatch.setattr(LocalFileStorage, "ler", lambda self, c: pytest.fail("leu o arquivo ao montar a tela"))

    at = AppTest.from_function(_tela_anexos, args=(bm_id,), default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    botoes = at.get("download_button")
    assert len(botoes) == 2
    assert {b.proto.label for b in botoes} == {"Baixar"}


@pytest.mark.parametrize(
    ("nome", "mime", "esperado"),
    [
        ("BM.pdf", None, "pdf"),
        ("BM.PDF", "application/octet-stream", "pdf"),
        ("arquivo", "application/pdf", "pdf"),
        ("foto.JPG", None, "imagem"),
        ("print", "image/png", "imagem"),
        ("planilha.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None),
    ],
)
def test_tipo_visualizavel(nome, mime, esperado):
    from sim.ui.common import tipo_visualizavel

    assert tipo_visualizavel(nome, mime) == esperado


def test_visualizar_abre_pdf_e_so_aparece_para_pdf_e_imagem(ambiente):
    from streamlit.testing.v1 import AppTest

    cc_id = asap.criar_centro_custo({**CC_ASAP, "titulo": "OBRA-VER"})
    bm_id = asap.criar_bm(bm_dados(cc_id), [arquivo("medicao.pdf", PDF), arquivo("planilha.xlsx", b"xlsx")])

    at = AppTest.from_function(_tela_anexos, args=(bm_id,), default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    visualizar = [b for b in at.button if b.label == "Visualizar"]
    assert len(visualizar) == 1  # só o PDF; a planilha só tem Baixar
    assert len(at.get("download_button")) == 2

    visualizar[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("medicao.pdf" in c.value for c in at.caption)
