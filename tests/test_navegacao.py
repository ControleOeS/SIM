"""Mapa de navegação, identidade visual e logotipos (sem Streamlit)."""
import hashlib
from pathlib import Path

from PIL import Image

from sim.ui import navegacao as nav
from sim.ui.tema import IDENTIDADES, LOGOS_DIR, caminho_logo, logo_data_uri

RAIZ = Path(__file__).resolve().parent.parent


def test_inicio_tem_exatamente_tres_areas():
    assert [titulo for _, _, titulo in nav.AREAS_INICIO] == ["ASAP", "SUPERUS", "Administrativo"]
    assert [ident for _, ident, _ in nav.AREAS_INICIO] == ["ASAP", "SUPERUS", "OES"]


def test_administrativo_oferece_asap_adm_e_superus_adm():
    assert nav.OPCOES_ADM == ("asap_adm", "sup_adm")
    assert [(nav.MODULOS[k].empresa, nav.MODULOS[k].tipo) for k in nav.OPCOES_ADM] == [("ASAP", "ADM"),
                                                                                     ("SUPERUS", "ADM")]


def test_cada_modulo_contem_so_telas_da_propria_empresa_e_tipo():
    prefixo = {("ASAP", "ENG"): "telas/asap_eng_", ("ASAP", "ADM"): "telas/asap_adm_",
               ("SUPERUS", "ENG"): "telas/superus_eng_", ("SUPERUS", "ADM"): "telas/superus_adm_"}
    for m in nav.MODULOS.values():
        assert m.telas, m.chave
        for t in m.telas:
            assert t.arquivo.startswith(prefixo[(m.empresa, m.tipo)]), (m.chave, t.arquivo)


def test_todas_as_telas_originais_continuam_registradas():
    arquivos = {t.arquivo for t in nav.todas_as_telas()}
    existentes = {f"telas/{p.name}" for p in (RAIZ / "telas").glob("*.py")}
    assert arquivos == existentes  # nenhuma tela perdida nem órfã
    for f in ["asap_eng_bm_mensal", "asap_eng_cadastro", "asap_adm_faturamento", "superus_eng_bm_mensal",
              "superus_eng_bm_semanal", "superus_eng_cadastro", "superus_eng_encerramento", "superus_eng_help",
              "superus_adm_faturamento", "superus_adm_planejamento", "superus_adm_atualizar_dados", "superus_adm_valor_previsto"]:
        assert f"telas/{f}.py" in arquivos


def test_urls_e_chaves_unicas():
    telas = nav.todas_as_telas()
    assert len({t.url for t in telas}) == len(telas)
    assert len({t.chave for t in telas}) == len(telas)


def test_modulo_da_tela():
    assert nav.modulo_da_tela("asap_bm").chave == "asap_eng"
    assert nav.modulo_da_tela("sup_fat").chave == "sup_adm"
    assert nav.modulo_da_tela("asap_adm").chave == "asap_adm"
    assert nav.modulo_da_tela("inicio") is None
    assert nav.modulo_da_tela("adm_selecao") is None


def test_migalhas():
    assert nav.migalhas("ASAP", "ENG", "BM Mensal") == ["O&S Gestão", "ASAP", "BM Mensal"]
    assert nav.migalhas("SUPERUS", "ADM", "Faturamento") == ["O&S Gestão", "Administrativo", "SUPERUS ADM",
                                                            "Faturamento"]
    assert nav.migalhas("SUPERUS", "ENG", None) == ["O&S Gestão", "SUPERUS"]


def test_areas_operacionais_sem_rotulo_engenharia():
    assert nav.nome_tipo("ASAP", "ENG") == ""
    assert nav.nome_tipo("ASAP", "ADM") == "Administrativo"
    assert nav.nome_tipo("SUPERUS", "ENG") == ""
    assert nav.NOME_EMPRESA == {"ASAP": "ASAP", "SUPERUS": "SUPERUS"}


def test_logotipos_oficiais_presentes_e_integros():
    esperados = {"OES": ("oes-gestao.jpg", (200, 200)), "ASAP": ("asap.png", (420, 476)),
                 "SUPERUS": ("superus-engenharia.png", (512, 512))}
    for codigo, (arquivo, tamanho) in esperados.items():
        caminho = caminho_logo(codigo)
        assert caminho == LOGOS_DIR / arquivo and caminho.is_file()
        with Image.open(caminho) as im:
            assert im.size == tamanho  # arquivo original, sem redimensionar
        assert logo_data_uri(codigo).startswith("data:image/")
        assert hashlib.sha256(caminho.read_bytes()).hexdigest()  # legível


def test_cores_vem_dos_logotipos():
    assert IDENTIDADES["OES"].cor == "#00495C"
    assert IDENTIDADES["ASAP"].cor == "#1641FF"
    assert (IDENTIDADES["SUPERUS"].cor, IDENTIDADES["SUPERUS"].cor_detalhe) == ("#25382D", "#97C03B")
