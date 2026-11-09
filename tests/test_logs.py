import logging

from sim.logging_setup import _FormatoSemSegredos


def test_log_mascara_senha_em_url_inclusive_em_excecao():
    fmt = _FormatoSemSegredos("%(message)s")
    try:
        raise RuntimeError("falha em mssql+pyodbc://usuario:SenhaSecreta@servidor/banco")
    except RuntimeError:
        import sys

        rec = logging.LogRecord("sim", logging.ERROR, __file__, 1, "conexão postgresql://u:outra@h/db", None,
                                sys.exc_info())
    texto = fmt.format(rec)
    assert "SenhaSecreta" not in texto and "outra@" not in texto
    assert "usuario:***@servidor" in texto
