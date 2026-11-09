"""Consistência do código carregado quando o servidor Streamlit fica aberto durante alterações.

Problema: o Streamlit reexecuta app.py e as telas a cada alteração, mas módulos já importados
(sim.ui.common, sim.ui.layout, serviços…) podem continuar na versão antiga. Telas novas chamando
componentes antigos geram erros como "cannot import name" ou "unexpected keyword argument".

Solução: a cada execução, comparamos a "assinatura" dos arquivos .py do pacote (caminho, data de
modificação e tamanho). Se algo mudou desde a última carga, TODOS os módulos do pacote são
descartados juntos, e as importações seguintes carregam a versão atual de forma consistente.
O estado fica num módulo sentinela em sys.modules, que não é afetado pelo descarte.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

_SENTINELA = "_sim_estado_de_carga"


def _estado() -> types.ModuleType:
    estado = sys.modules.get(_SENTINELA)
    if estado is None:
        estado = types.ModuleType(_SENTINELA)
        estado.assinaturas = {}
        sys.modules[_SENTINELA] = estado
    return estado


def assinatura(raiz: Path) -> tuple:
    itens = []
    for p in sorted(Path(raiz).rglob("*.py")):
        try:
            s = p.stat()
        except OSError:
            continue
        itens.append((str(p), s.st_mtime_ns, s.st_size))
    return tuple(itens)


def descartar_modulos_alterados(raiz: Path, pacote: str) -> bool:
    """Descarta todos os módulos de `pacote` se algum arquivo em `raiz` mudou desde a última chamada.

    Retorna True quando houve descarte. Na primeira chamada só registra a assinatura atual.
    """
    estado = _estado()
    atual = assinatura(raiz)
    anterior = estado.assinaturas.get(pacote)
    estado.assinaturas[pacote] = atual
    if anterior is None or anterior == atual:
        return False
    for nome in [m for m in sys.modules if m == pacote or m.startswith(pacote + ".")]:
        del sys.modules[nome]
    return True
