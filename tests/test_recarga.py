"""Regressão: servidor aberto durante alterações misturava módulos antigos e novos
(ImportError 'ICONE' e TypeError 'tela' observados após o redesign)."""
import importlib
import logging
import os
import sys
import time

from sim.recarga import descartar_modulos_alterados


def _escrever(caminho, texto):
    caminho.write_text(texto, encoding="utf-8")
    # garante data de modificação diferente mesmo em sistemas de arquivos com baixa resolução
    t = time.time() + 5
    os.utime(caminho, (t, t))


def test_modulos_alterados_sao_descartados_juntos(tmp_path, monkeypatch):
    pkg = tmp_path / "pkgsim"
    (pkg / "ui").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "ui" / "__init__.py").write_text("", encoding="utf-8")
    common = pkg / "ui" / "common.py"
    common.write_text("def cabecalho(titulo):\n    return titulo\n", encoding="utf-8")
    (pkg / "ui" / "layout.py").write_text("from pkgsim.ui.common import cabecalho\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))

    # 1ª execução: registra a assinatura e carrega a versão antiga
    assert descartar_modulos_alterados(pkg, "pkgsim") is False
    antigo = importlib.import_module("pkgsim.ui.common")
    importlib.import_module("pkgsim.ui.layout")
    assert not hasattr(antigo, "ICONE")

    # sem mudanças: nada é descartado
    assert descartar_modulos_alterados(pkg, "pkgsim") is False
    assert "pkgsim.ui.common" in sys.modules

    # código alterado com o "servidor" aberto (como no redesign)
    _escrever(common, "ICONE = {'salvar': 'x'}\ndef cabecalho(titulo, tela=None):\n    return titulo\n")
    assert descartar_modulos_alterados(pkg, "pkgsim") is True
    assert not any(m == "pkgsim" or m.startswith("pkgsim.") for m in sys.modules)

    from pkgsim.ui.common import ICONE, cabecalho  # antes: ImportError / TypeError

    assert ICONE["salvar"] == "x"
    assert cabecalho("t", tela=None) == "t"
    for m in [m for m in sys.modules if m.startswith("pkgsim")]:
        del sys.modules[m]


def test_configurar_logs_nao_duplica_handler_apos_recarga(tmp_path, monkeypatch):
    monkeypatch.setenv("SIM_LOGS_DIR", str(tmp_path / "logs"))
    import sim.logging_setup as ls
    from sim.config import load_settings

    logger = logging.getLogger(ls.LOGGER_NAME)
    antes = list(logger.handlers)
    try:
        ls.configurar_logs(load_settings())
        recarregado = importlib.reload(ls)  # simula o descarte do módulo
        recarregado.configurar_logs(load_settings())
        marcados = [h for h in logger.handlers if getattr(h, recarregado._MARCA_HANDLER, False)]
        assert len(marcados) == 1
    finally:
        for h in list(logger.handlers):
            if h not in antes:
                logger.removeHandler(h)
                h.close()
