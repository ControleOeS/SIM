"""Componentes comuns das telas.

Padrões adotados (correções dos defeitos do original):
- Mensagem de sucesso só depois do retorno do serviço (commit confirmado).
- Em erro, o formulário mantém o que foi digitado (as chaves dos campos não mudam).
- Após sucesso, o formulário e a seleção da tabela são reiniciados (nova "versão" de chaves).
"""
from __future__ import annotations

from typing import Callable, Iterable, Sequence

import pandas as pd
import streamlit as st

from sim.errors import NotFoundError, PersistenceError, SimError, ValidationError
from sim.formatters import formatar_data_hora, formatar_moeda, formatar_numero
from sim.logging_setup import get_logger, nova_referencia
from sim.options import Opcoes
from sim.storage import ArquivoNovo

log = get_logger("ui")

# Ícones padronizados (Material Symbols, nativos do Streamlit)
ICONE = {
    "salvar": ":material/save:",
    "cancelar": ":material/close:",
    "limpar": ":material/restart_alt:",
    "excluir": ":material/delete:",
    "filtro_limpar": ":material/filter_alt_off:",
    "baixar": ":material/download:",
    "visualizar": ":material/visibility:",
    "ok": ":material/check:",
    "voltar": ":material/arrow_back:",
    "trocar": ":material/swap_horiz:",
}

_PADRAO = object()


# --------------------------------------------------------- cabeçalho ----


def cabecalho(empresa: str, modulo: str, titulo: str, subtitulo: str = "", tela=_PADRAO) -> None:
    """Cabeçalho padrão: O&S + migalhas + logotipo da coligada, chips do módulo e título.

    `tela` é o último item das migalhas (padrão: o próprio título; None na tela inicial do módulo).
    """
    from sim.ui import navegacao
    from sim.ui.layout import titulo_tela, topo

    topo(navegacao.migalhas(empresa, modulo, titulo if tela is _PADRAO else tela), coligada=empresa)
    titulo_tela(empresa, modulo, titulo, subtitulo)
    mostrar_flash()


def secao(titulo: str) -> None:
    from sim.ui.layout import secao as _secao

    _secao(titulo)


# ------------------------------------------------- estado / mensagens ----


def flash(mensagem: str, tipo: str = "success") -> None:
    st.session_state.setdefault("_flash", []).append((tipo, mensagem))


def mostrar_flash() -> None:
    for tipo, msg in st.session_state.pop("_flash", []):
        if tipo == "success":
            st.success(msg, icon=":material/check_circle:")
        elif tipo == "warning":
            st.warning(msg)
        else:
            st.info(msg)


def versao(ns: str) -> int:
    return st.session_state.setdefault(f"_v_{ns}", 0)


def reiniciar(ns: str) -> None:
    """Gera novas chaves para o formulário/tabela do namespace e limpa erros."""
    st.session_state[f"_v_{ns}"] = versao(ns) + 1
    _limpar_erros(ns)


def chave(ns: str, nome: str, *extra: object) -> str:
    return "|".join([ns, str(versao(ns)), nome, *map(str, extra)])


def versao_lida(ns: str, registro, ctx: object = "") -> int | None:
    """Versão do registro no momento em que o formulário de edição foi aberto.

    Fica guardada enquanto o mesmo formulário estiver na tela (mesmo namespace, versão de chaves e
    `ctx`), para o serviço recusar a gravação se outra pessoa alterou o registro nesse meio tempo.
    Chame com `registro=None` sempre que nenhum registro estiver em edição, para esquecer a anterior.
    """
    k = f"_versao_lida_{ns}"
    if registro is None:
        st.session_state.pop(k, None)
        return None
    marca = (versao(ns), str(ctx))
    guardado = st.session_state.get(k)
    if guardado is None or guardado[0] != marca:
        guardado = st.session_state[k] = (marca, registro.versao)
    return guardado[1]


def _comparavel(valor):
    """Valor de um campo para comparação entre execuções (arquivos enviados viram seus IDs)."""
    if isinstance(valor, (list, tuple)) and any(hasattr(v, "file_id") for v in valor):
        return tuple(getattr(v, "file_id", v) for v in valor)
    return getattr(valor, "file_id", valor)


def _valores_dos_campos(ns: str) -> dict:
    prefixo = f"{ns}|{versao(ns)}|"
    return {
        k: _comparavel(st.session_state[k])
        for k in list(st.session_state.keys())
        if isinstance(k, str) and k.startswith(prefixo)
    }


def _guardar_erros(ns: str, mensagens: dict[str, str]) -> None:
    """Guarda os erros junto com os valores dos campos no momento da tentativa de salvar."""
    st.session_state[f"_erros_{ns}"] = mensagens
    st.session_state[f"_erros_campos_{ns}"] = _valores_dos_campos(ns)


def _limpar_erros(ns: str) -> None:
    st.session_state.pop(f"_erros_{ns}", None)
    st.session_state.pop(f"_erros_campos_{ns}", None)


def erros(ns: str) -> dict[str, str]:
    """Erros da última tentativa de salvar. Somem assim que o usuário altera qualquer campo do formulário
    (o SIM volta a conferir na próxima tentativa de salvar)."""
    mensagens = st.session_state.get(f"_erros_{ns}", {})
    if mensagens and _valores_dos_campos(ns) != st.session_state.get(f"_erros_campos_{ns}"):
        _limpar_erros(ns)
        return {}
    return mensagens


def erro_campo(ns: str, campo: str) -> None:
    msg = erros(ns).get(campo)
    if msg:
        st.markdown(f":red[{msg}]")


def resumo_erros(ns: str, rotulos: dict[str, str]) -> None:
    e = erros(ns)
    if e:
        itens = "\n".join(f"- **{rotulos.get(k, k)}**: {v}" for k, v in e.items())
        st.error(f"Não foi possível salvar. Corrija os campos abaixo:\n\n{itens}", icon=":material/error:")


def executar(ns: str, acao: Callable[[], object], sucesso: str, *, reiniciar_ns: Iterable[str] = ()) -> bool:
    """Executa uma gravação e trata os erros de forma compreensível.

    Retorna True em sucesso (e faz st.rerun). Em erro, mantém o formulário preenchido.
    """
    _limpar_erros(ns)
    try:
        with st.spinner("Salvando…"):
            acao()
    except ValidationError as exc:
        _guardar_erros(ns, exc.errors)
        st.rerun()
    except NotFoundError as exc:
        st.error(exc.message, icon=":material/error:")
        return False
    except PersistenceError as exc:
        st.error(exc.message, icon=":material/error:")
        return False
    except SimError as exc:
        st.error(exc.message, icon=":material/error:")
        return False
    except Exception:  # erro inesperado: registra e mostra referência
        ref = nova_referencia()
        log.exception("[%s] Erro inesperado na tela (%s)", ref, ns)
        st.error(f"Ocorreu um erro inesperado. Nada foi confirmado. Referência: {ref}", icon=":material/error:")
        return False
    flash(sucesso)
    reiniciar(ns)
    for outro in reiniciar_ns:
        reiniciar(outro)
    st.rerun()
    return True  # pragma: no cover


def carregar(fn: Callable, *args, **kwargs):
    """Executa uma consulta; em falha técnica mostra a mensagem e interrompe a tela."""
    try:
        return fn(*args, **kwargs)
    except SimError as exc:
        st.error(exc.message, icon=":material/error:")
        st.stop()


# ------------------------------------------------------------ campos ----


def texto_inicial_moeda(valor) -> str:
    return formatar_moeda(valor)


def campo_texto(ns: str, campo: str, rotulo: str, valor: str | None = "", *, obrigatorio=False, area=False,
                ajuda: str | None = None, max_chars: int | None = 255, ctx: object = "") -> str:
    label = f"{rotulo} *" if obrigatorio else rotulo
    k = chave(ns, campo, ctx)
    if area:
        r = st.text_area(label, value=valor or "", key=k, help=ajuda)
    else:
        r = st.text_input(label, value=valor or "", key=k, help=ajuda, max_chars=max_chars)
    erro_campo(ns, campo)
    return r


def campo_moeda(ns: str, campo: str, rotulo: str, valor=None, *, obrigatorio=False, ajuda: str | None = None,
                ctx: object = "") -> str:
    label = f"{rotulo} *" if obrigatorio else rotulo
    r = st.text_input(label, value=formatar_moeda(valor), key=chave(ns, campo, ctx), placeholder="0,00",
                      help=ajuda or "Formato brasileiro, ex.: 1.234,56")
    erro_campo(ns, campo)
    return r


def campo_numero(ns: str, campo: str, rotulo: str, valor=None, *, obrigatorio=False, ajuda: str | None = None,
                 ctx: object = "") -> str:
    label = f"{rotulo} *" if obrigatorio else rotulo
    r = st.text_input(label, value=formatar_numero(valor), key=chave(ns, campo, ctx), help=ajuda)
    erro_campo(ns, campo)
    return r


def campo_escolha(ns: str, campo: str, rotulo: str, opcoes: Opcoes | Sequence[str], atual: str | None = None, *,
                  obrigatorio=False, ctx: object = "", ajuda: str | None = None) -> str | None:
    if isinstance(opcoes, Opcoes):
        lista = opcoes.com_valor_atual(atual)
        if opcoes.provisorio:
            ajuda = (ajuda + "\n\n" if ajuda else "") + (
                "⚠ Opções provisórias: os valores reais da lista SharePoint ainda não foram confirmados. "
                "Ajuste em config/opcoes.json."
            )
            rotulo = f"{rotulo} ⚠"
    else:
        lista = list(opcoes)
        if atual and atual not in lista:
            lista.insert(0, atual)
    label = f"{rotulo} *" if obrigatorio else rotulo
    idx = lista.index(atual) if atual in lista else None
    r = st.selectbox(label, lista, index=idx, key=chave(ns, campo, ctx), placeholder="Selecione", help=ajuda)
    erro_campo(ns, campo)
    return r


def campo_anexos(ns: str, rotulo: str = "Anexos", *, obrigatorio=False, ctx: object = "") -> list[ArquivoNovo]:
    label = f"{rotulo} *" if obrigatorio else rotulo
    arquivos = st.file_uploader(label, accept_multiple_files=True, key=chave(ns, "anexos_up", ctx))
    erro_campo(ns, "anexos")
    return [ArquivoNovo(nome=a.name, conteudo=a.getvalue(), tipo_mime=a.type) for a in (arquivos or [])]


def _tamanho(n: int) -> str:
    from decimal import Decimal

    kb = (Decimal(n) / 1024).quantize(Decimal("0.1"))
    return f"{formatar_numero(kb)} KB"


_EXTENSOES_IMAGEM = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


def _nome_arquivo(nome_original: str) -> str:
    return nome_original.replace("\\", "/").split("/")[-1]


def tipo_visualizavel(nome: str, tipo_mime: str | None) -> str | None:
    """'pdf', 'imagem' ou None (só pode ser baixado)."""
    nome, mime = nome.lower(), (tipo_mime or "").lower()
    if mime == "application/pdf" or nome.endswith(".pdf"):
        return "pdf"
    if mime.startswith("image/") or nome.endswith(_EXTENSOES_IMAGEM):
        return "imagem"
    return None


@st.dialog("Visualizar anexo", width="large")
def _visualizar_anexo(anexo_id: int) -> None:
    from sim.services.common import ler_anexo

    try:
        meta, conteudo = ler_anexo(anexo_id)  # confere a permissão de novo
    except SimError as exc:
        st.error(exc.message)
        return
    nome = _nome_arquivo(meta.nome_original)
    st.caption(f":material/attach_file: {nome} · {_tamanho(meta.tamanho_bytes)}")
    if tipo_visualizavel(nome, meta.tipo_mime) == "pdf":
        st.pdf(conteudo, height=720, key=f"pdf-{anexo_id}", alt=nome)
    else:
        st.image(conteudo, caption=nome)
    st.download_button("Baixar", conteudo, file_name=nome, mime=meta.tipo_mime or "application/octet-stream",
                       key=f"dl-visualizar-{anexo_id}", on_click="ignore", icon=ICONE["baixar"])


def anexos_download(ns: str, anexos: Sequence, *, ctx: object = "") -> None:
    """Anexos gravados com botões Visualizar (PDF e imagens) e Baixar (fora de st.form).

    O conteúdo só é lido do armazenamento quando a pessoa clica em Visualizar ou Baixar;
    antes disso a tela apenas confere permissão e existência do arquivo.
    """
    from sim.services.common import carregador_anexo, verificar_anexo

    if not anexos:
        st.caption("Nenhum anexo gravado.")
        return
    st.markdown("**Anexos gravados**")
    for a in anexos:
        c1, c2, c3 = st.columns([3, 1, 1], vertical_alignment="center")
        c1.markdown(f":material/attach_file: {a.nome_original} · {_tamanho(a.tamanho_bytes)}")
        try:
            meta = verificar_anexo(a.id)
            nome = _nome_arquivo(meta.nome_original)
            if tipo_visualizavel(nome, meta.tipo_mime) and c2.button(
                "Visualizar", key=chave(ns, "ver", ctx, a.id), icon=ICONE["visualizar"]
            ):
                _visualizar_anexo(meta.id)
            c3.download_button("Baixar", carregador_anexo(meta.id), file_name=nome,
                               mime=meta.tipo_mime or "application/octet-stream",
                               key=chave(ns, "dl", ctx, a.id), on_click="ignore", icon=ICONE["baixar"])
        except SimError as exc:
            c3.caption(f":red[{exc.message}]")


def anexos_remover(ns: str, anexos: Sequence, *, ctx: object = "") -> list[int]:
    """Seleção dos anexos a remover ao salvar (pode ficar dentro de st.form)."""
    if not anexos:
        return []
    nomes = {a.id: a.nome_original for a in anexos}
    return st.multiselect("Remover anexos ao salvar", list(nomes), format_func=lambda i: nomes[i],
                          key=chave(ns, "remover", ctx), placeholder="Nenhum (manter todos)")


# ------------------------------------------------------------ tabela ----


def tabela(ns: str, linhas: list[dict], *, selecionavel=True, altura: int | None = None, ctx: object = "") -> int | None:
    """Mostra a tabela e devolve o ID da linha selecionada (coluna 'ID').

    `ctx` deve mudar quando os filtros mudam: a seleção é descartada, evitando que
    um índice de linha antigo aponte para outro registro.
    """
    if not linhas:
        from sim.ui.layout import estado_vazio

        estado_vazio("Nenhum registro encontrado.", "Ajuste os filtros ou cadastre um novo registro.")
        return None
    df = pd.DataFrame(linhas)
    kwargs = dict(hide_index=True, width="stretch")
    if altura:
        kwargs["height"] = altura
    if not selecionavel:
        st.dataframe(df, **kwargs)
        return None
    evento = st.dataframe(df, key=chave(ns, "tabela", ctx), on_select="rerun", selection_mode="single-row", **kwargs)
    linhas_sel = evento.selection.rows if evento and evento.selection else []
    if not linhas_sel:
        return None
    return int(df.iloc[linhas_sel[0]]["ID"])


def moeda(v) -> str:
    return formatar_moeda(v)


def data_hora(v) -> str:
    return formatar_data_hora(v)


def qtd_anexos(anexos) -> str:
    n = len(anexos or [])
    return f"📎 {n}" if n else "—"


# ----------------------------------------------------------- exclusão ----


@st.dialog("Excluir registro")
def confirmar_exclusao(ns: str, descricao: str, acao: Callable[[], None], sucesso: str) -> None:
    st.warning("Deseja mesmo excluir essa linha? Sua ação não terá volta!", icon=":material/warning:")
    st.markdown(descricao)
    c1, c2 = st.columns(2)
    if c1.button("Sim, excluir", width="stretch", icon=ICONE["excluir"], key="confirmar-exclusao"):
        try:
            with st.spinner("Excluindo…"):
                acao()
        except SimError as exc:
            st.error(exc.descricao(), icon=":material/error:")
            return
        flash(sucesso)
        reiniciar(ns)
        st.rerun()
    if c2.button("Não, voltar", width="stretch", icon=ICONE["cancelar"], key="cancelar-exclusao"):
        st.rerun()


def botao_excluir(ns: str, rotulo: str, ctx: object) -> bool:
    """Botão de exclusão em vermelho (estilo em sim/ui/tema.py, classe st-key-excluir…)."""
    return st.button(rotulo, icon=ICONE["excluir"], key=f"excluir-{ns}-{versao(ns)}-{ctx}")


def formulario():
    """Área com borda para os campos de um formulário de dados.

    Não usa st.form: cada alteração chega ao SIM na hora, então a mensagem de erro some assim que o usuário
    muda um campo (ver `erros`) e informações como o valor previsto acompanham o que foi escolhido.
    """
    return st.container(border=True)


def botoes_formulario(editando: bool, *, rotulo_salvar: str | None = None,
                      rotulo_cancelar: str | None = None) -> tuple[bool, bool]:
    """Par padrão Salvar (primário) / Cancelar (secundário) no fim de `formulario()`."""
    b1, b2, _ = st.columns([1, 1, 2.5])
    salvar = b1.button(rotulo_salvar or ("Salvar alterações" if editando else "Salvar"),
                       type="primary", width="stretch", icon=ICONE["salvar"])
    cancelar = b2.button(rotulo_cancelar or ("Cancelar edição" if editando else "Limpar"),
                         width="stretch", icon=ICONE["cancelar"] if editando else ICONE["limpar"])
    return salvar, cancelar
