"""Regras do SIM SUPERUS e do SIM SUPERUS — Administrativo.

Diferenças em relação ao original (documentadas no README):
- O vínculo BM -> CC é feito e filtrado pelo ID do centro de custo, não pelo Título.
- Edições exigem um registro existente; Faturamento e Atualizar dados nunca criam registros.
- A regra dos 95% citada na tela Encerramento não existe nas fórmulas e não foi implementada.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from sim.auth import escopos_centros, exigir_area_adm, exigir_area_obras, exigir_centro, exigir_controlador
from sim.errors import NotFoundError, ValidationError
from sim.formatters import FUSO_LOCAL, normalizar_chave, para_local
from sim.models import SuperusBMMensal, SuperusBMMensalItem, SuperusBMSemanal, SuperusCentroCusto
from sim.options import opcoes
from sim.repositories.base import EmpresaRepository
from sim.repositories.superus import (
    SuperusBMMensalRepository,
    SuperusBMSemanalRepository,
    SuperusCentroCustoRepository,
)
from sim.services.common import (
    Validador,
    conferir_versao,
    contar_anexos_finais,
    leitura,
    transacao,
    validar_arquivos,
)
from sim.services import previsto
from sim.services.encerramento import verificar_cc_ativo
from sim.storage import ArquivoNovo

EMPRESA = "SUPERUS"

# Critério de duplicidade do Cadastro: o código do CC (Título) identifica o centro
# de custo — é por ele que o usuário localiza o CC nas telas Mensal/Semanal, e o
# aviso do original pede para conferir "o seu código" antes de cadastrar.
# Comparação sem diferenciar maiúsculas e ignorando espaços extras.
CRITERIO_DUPLICIDADE = "Título (código do CC) igual, sem diferenciar maiúsculas/minúsculas e espaços extras."


def status_permitidos_engenharia(status_atual: str | None = None) -> list[str]:
    """BM Mensal SUPERUS: só 'BM em Análise do Cliente' e 'BM Aprovado pelo Cliente'.

    Na edição, um status já gravado por outra área (ex.: faturamento) pode ser
    mantido, mas não pode ser escolhido como novo valor.
    """
    return opcoes("superus.status_engenharia").com_valor_atual(status_atual)


# ------------------------------------------------- centros de custo ----


def listar_centros_custo() -> Sequence[SuperusCentroCusto]:
    permitidos = escopos_centros(EMPRESA)
    with leitura() as s:
        centros = SuperusCentroCustoRepository(s).listar()
        return centros if permitidos is None else [c for c in centros if c.id in permitidos]


def obter_centro_custo(cc_id: int) -> SuperusCentroCusto:
    with leitura() as s:
        cc = SuperusCentroCustoRepository(s).get(cc_id)
        if cc is None:
            raise NotFoundError("Centro de custo não encontrado.")
        exigir_centro(EMPRESA, cc_id)
        return cc


# O módulo SUPERUS reúne os centros de custo destas coligadas (decisão de 2026-10-27).
COLIGADAS = ("SUPERUS ENGENHARIA", "ACPL", "SUPERUS HOLDING")


def _validar_cadastro(dados: dict) -> dict:
    v = Validador()
    v.escolha("coligada", dados.get("coligada"), COLIGADAS, obrigatorio=True)
    v.texto("titulo", dados.get("titulo"), obrigatorio=True)
    v.texto("gestor_obra", dados.get("gestor_obra"), obrigatorio=True)
    v.texto("obra_cliente", dados.get("obra_cliente"), obrigatorio=True)
    v.dia_do_mes("inicio_medicao", dados.get("inicio_medicao"), obrigatorio=True)
    v.dia_do_mes("fim_medicao", dados.get("fim_medicao"), obrigatorio=True)
    return v.verificar()


def criar_centro_custo(dados: dict) -> int:
    exigir_controlador()
    valores = _validar_cadastro(dados)
    chave = normalizar_chave(valores["titulo"])
    with transacao("superus.criar_centro_custo") as tx:
        repo = SuperusCentroCustoRepository(tx.session)
        existente = repo.por_chave(chave)
        if existente:
            raise ValidationError(
                {"titulo": f"O centro de custo '{existente.titulo}' já está cadastrado ({existente.obra_cliente})."}
            )
        empresa = EmpresaRepository(tx.session).por_codigo(EMPRESA)
        cc = repo.add(SuperusCentroCusto(empresa_id=empresa.id, titulo_chave=chave, **valores))
        return cc.id


def atualizar_cadastro(cc_id: int, dados: dict, *, versao: int | None = None) -> None:
    """Edição completa do cadastro (camada de serviço; não há tela no original)."""
    exigir_centro(EMPRESA, cc_id, escrita=True)
    valores = _validar_cadastro(dados)
    chave = normalizar_chave(valores["titulo"])
    with transacao("superus.atualizar_cadastro") as tx:
        repo = SuperusCentroCustoRepository(tx.session)
        cc = repo.get(cc_id)
        if cc is None:
            raise NotFoundError("Centro de custo não encontrado.")
        conferir_versao(cc, versao)
        outro = repo.por_chave(chave)
        if outro and outro.id != cc_id:
            raise ValidationError({"titulo": "Já existe outro centro de custo com este título."})
        for k, val in valores.items():
            setattr(cc, k, val)
        cc.titulo_chave = chave


def excluir_centro_custo(cc_id: int, *, versao: int | None = None) -> None:
    exigir_centro(EMPRESA, cc_id, escrita=True)
    with transacao("superus.excluir_centro_custo") as tx:
        repo = SuperusCentroCustoRepository(tx.session)
        cc = repo.get(cc_id)
        if cc is None:
            raise NotFoundError("Centro de custo não encontrado.")
        conferir_versao(cc, versao)
        if repo.possui_bms(cc_id):
            raise ValidationError({"centro_custo": "Este centro de custo tem BMs vinculados e não pode ser excluído."})
        repo.delete(cc)


def atualizar_dados_cc(
    cc_id: int, *, qtd_bms: object, cidade: object, numero_contrato: object, versao: int | None = None
) -> None:
    """SIM SUPERUS ADM, 'Atualizar dados': Qtd_BMs, Cidade e Nº do Contrato de um CC existente."""
    exigir_area_adm()
    exigir_centro(EMPRESA, cc_id, escrita=True)
    v = Validador()
    v.numero("qtd_bms", qtd_bms)
    v.texto("cidade", cidade)
    v.texto("numero_contrato", numero_contrato)
    valores = v.verificar()
    with transacao("superus.atualizar_dados_cc") as tx:
        cc = SuperusCentroCustoRepository(tx.session).get(cc_id)
        if cc is None:
            raise NotFoundError("Centro de custo não encontrado; nada foi gravado.")
        conferir_versao(cc, versao)
        for k, val in valores.items():
            setattr(cc, k, val)


# --------------------------------------------------------- BM Mensal ----


def _pasta_mensal(bm_id: int) -> str:
    return f"superus/bm_mensal/{bm_id}"


def _pasta_semanal(bm_id: int) -> str:
    return f"superus/bm_semanal/{bm_id}"


def _validar_mensal(dados: dict, atual: SuperusBMMensal | None) -> Validador:
    v = Validador()
    v.texto("titulo", dados.get("titulo"), obrigatorio=True)
    _escolher_mes(v, dados.get("mes_referencia"), atual)
    v.escolha("tipo", dados.get("tipo"), opcoes("superus.tipo").com_valor_atual(atual and atual.tipo), obrigatorio=True)
    if "itens" in dados:
        _validar_itens(v, dados["itens"])
    else:  # sem a lista de BMs (uso interno e testes): valores informados diretamente
        v.moeda("valor_bm", dados.get("valor_bm"), obrigatorio=True)
        v.moeda("valor_aprovado", dados.get("valor_aprovado"))
    v.moeda("glosa", dados.get("glosa"))
    v.moeda("postergado", dados.get("postergado"))
    v.escolha("status", dados.get("status"), status_permitidos_engenharia(atual and atual.status), obrigatorio=True)
    v.texto("cidade", dados.get("cidade"), obrigatorio=True)
    v.texto("numero_contrato", dados.get("numero_contrato"), obrigatorio=True)
    v.texto("po", dados.get("po"))
    v.texto(previsto.CAMPO_JUSTIFICATIVA, dados.get(previsto.CAMPO_JUSTIFICATIVA), max_len=4000)
    return v


# Uma resposta por mês (decisão do responsável em 2026-10-27): o gestor anexa todos os BMs do mês na mesma resposta
# e informa o valor somado. O ano não é digitado: vem da data do lançamento.


def _hoje() -> date:
    return datetime.now(FUSO_LOCAL).date() if FUSO_LOCAL else date.today()


def meses_permitidos(referencia: date | None = None) -> list[str]:
    """Meses que podem ser lançados na data de referência: de janeiro até o mês atual (um mês só fica disponível
    a partir do dia 1º dele). Em janeiro, também dezembro, que é do ano anterior."""
    meses = list(opcoes("superus.mes_referencia").valores)
    ref = referencia or _hoje()
    permitidos = meses[: ref.month]
    if ref.month == 1:
        permitidos.append(meses[-1])
    return permitidos


def ano_do_mes(mes: str | None, referencia: date | None = None) -> str | None:
    """Ano do BM a partir do mês escolhido: o ano da data de referência (hoje, no lançamento), exceto dezembro
    lançado em janeiro, que é do ano anterior. Mês ainda não permitido -> None."""
    ref = referencia or _hoje()
    if mes not in meses_permitidos(ref):
        return None
    dezembro = opcoes("superus.mes_referencia").valores[-1]
    return str(ref.year - 1 if ref.month == 1 and mes == dezembro else ref.year)


def _data_de_referencia(bm: SuperusBMMensal | None) -> date:
    """Novo BM: hoje. Edição: a data em que o BM foi lançado."""
    return _hoje() if bm is None else para_local(bm.criado_em).date()


def meses_para(bm: SuperusBMMensal | None = None) -> list[str]:
    """Opções de mês do formulário. Na edição, o mês já gravado continua disponível."""
    meses = meses_permitidos(_data_de_referencia(bm))
    if bm is not None and bm.mes_referencia not in meses:
        meses.insert(0, bm.mes_referencia)
    return meses


def ano_de_referencia(mes: str | None, bm: SuperusBMMensal | None = None) -> str | None:
    """Novo BM: ano pela data de hoje. Edição: mantém o ano gravado; se o mês mudar, recalcula pela data em que o
    BM foi lançado."""
    if bm is not None and mes == bm.mes_referencia:
        return bm.ano
    return ano_do_mes(mes, _data_de_referencia(bm))


def _escolher_mes(v: Validador, mes: object, bm: SuperusBMMensal | None) -> None:
    v.escolha("mes_referencia", mes, meses_para(bm), obrigatorio=True)
    if mes in opcoes("superus.mes_referencia").valores and mes not in meses_para(bm):
        v.erros["mes_referencia"] = (f"{mes} ainda não pode ser lançado: cada mês só fica disponível a partir do "
                                     "dia 1º dele.")


def _bm_do_mes(session, centro_custo_id: int, ano: str | None, mes: str | None, ignorar_id: int | None = None):
    if not ano or not mes:
        return None
    consulta = select(SuperusBMMensal).where(
        SuperusBMMensal.centro_custo_id == centro_custo_id,
        SuperusBMMensal.ano == ano,
        SuperusBMMensal.mes_referencia == mes,
    )
    if ignorar_id is not None:
        consulta = consulta.where(SuperusBMMensal.id != ignorar_id)
    return session.scalar(consulta.order_by(SuperusBMMensal.id).limit(1))


def bm_do_mes(centro_custo_id: int, mes: str | None, bm: SuperusBMMensal | None = None) -> int | None:
    """ID do BM que já ocupa o mês no CC (para a tela avisar antes de salvar)."""
    exigir_centro(EMPRESA, centro_custo_id)
    with leitura() as s:
        existente = _bm_do_mes(s, centro_custo_id, ano_de_referencia(mes, bm), mes, bm and bm.id)
        return existente.id if existente else None


def mensagem_mes_ocupado(bm_id: int, mes: str, ano: str) -> str:
    return (f"Já existe o BM #{bm_id} de {mes}/{ano} neste centro de custo. Cada mês tem uma única resposta: "
            f"edite o BM #{bm_id}, anexe nele todos os BMs do mês e informe o valor somado.")


def _conferir_mes_livre(v: Validador, session, centro_custo_id: int, ignorar_id: int | None = None) -> None:
    mes, ano = v.valores.get("mes_referencia"), v.valores.get("ano")
    existente = _bm_do_mes(session, centro_custo_id, ano, mes, ignorar_id)
    if existente:
        v.erro("mes_referencia", mensagem_mes_ocupado(existente.id, mes, ano))


def _gravar_mes_unico(session, ano: str, mes: str) -> None:
    """O índice único do banco segura dois lançamentos simultâneos do mesmo mês."""
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValidationError({"mes_referencia": f"Já existe um BM de {mes}/{ano} neste centro de custo. "
                                                 "Atualize a página e edite o BM existente."}) from exc


def _vazio(valor: object) -> bool:
    return valor is None or (isinstance(valor, float) and valor != valor) or str(valor).strip() == ""


def _validar_itens(v: Validador, itens: list[dict]) -> None:
    """Lista de BMs da resposta do mês: identificação e valor obrigatórios, valor aprovado opcional.

    Valor BM/PO e Valor Aprovado passam a ser as somas (não são digitados). Linhas totalmente vazias são ignoradas.
    """
    linhas = [i for i in itens or [] if not all(_vazio(i.get(c)) for c in ("descricao", "valor_bm", "valor_aprovado"))]
    if not linhas:
        v.erro("itens", "Inclua pelo menos um BM com o valor.")
        return
    problemas, novos = [], []
    for n, item in enumerate(linhas, 1):
        lv = Validador()
        lv.texto("descricao", item.get("descricao"), obrigatorio=True)
        lv.moeda("valor_bm", None if _vazio(item.get("valor_bm")) else item.get("valor_bm"), obrigatorio=True)
        lv.moeda("valor_aprovado", None if _vazio(item.get("valor_aprovado")) else item.get("valor_aprovado"))
        if lv.erros:
            rotulos = {"descricao": "identificação", "valor_bm": "valor do BM", "valor_aprovado": "valor aprovado"}
            problemas.append(f"BM {n}: " + "; ".join(f"{rotulos[c]}: {m.lower()}" for c, m in lv.erros.items()))
            continue
        novos.append(SuperusBMMensalItem(ordem=n, **lv.valores))
    if problemas:
        v.erro("itens", " · ".join(problemas))
        return
    v.valores["itens"] = novos
    v.valores["valor_bm"] = sum((i.valor_bm for i in novos), Decimal(0))
    aprovados = [i.valor_aprovado for i in novos if i.valor_aprovado is not None]
    v.valores["valor_aprovado"] = sum(aprovados, Decimal(0)) if aprovados else None


def listar_bms_mensais(
    *, centro_custo_id: int | None = None, mes: str | None = None, status: str | None = None, po: str | None = None
):
    permitidos = escopos_centros(EMPRESA)
    if centro_custo_id is not None:
        exigir_centro(EMPRESA, centro_custo_id)
    with leitura() as s:
        return SuperusBMMensalRepository(s).listar(
            centro_custo_id=centro_custo_id,
            centro_custo_ids=permitidos,
            mes=mes,
            status=status,
            po=po,
        )


def obter_bm_mensal(bm_id: int) -> SuperusBMMensal:
    with leitura() as s:
        bm = SuperusBMMensalRepository(s).get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM não encontrado. Ele pode ter sido excluído.")
        exigir_centro(EMPRESA, bm.centro_custo_id)
        return bm


def criar_bm_mensal(centro_custo_id: int, dados: dict, anexos: list[ArquivoNovo]) -> int:
    exigir_area_obras()
    """O CC vem da seleção confirmada pelo usuário (varObraAtual), nunca do formulário."""
    exigir_centro(EMPRESA, centro_custo_id, escrita=True)
    v = _validar_mensal(dados, None)
    v.valores["ano"] = ano_de_referencia(v.valores.get("mes_referencia"))
    if not anexos:
        v.erro("anexos", "Adicione pelo menos um anexo.")
    with transacao("superus.criar_bm_mensal") as tx:
        cc = SuperusCentroCustoRepository(tx.session).get(centro_custo_id)
        if cc is None:
            raise ValidationError({"centro_custo_id": "Centro de custo inexistente."})
        verificar_cc_ativo(cc)
        _conferir_mes_livre(v, tx.session, centro_custo_id)
        previsto.conferir_variacao(
            v, previsto.previsto_de(tx.session, centro_custo_id, v.valores.get("ano"), v.valores.get("mes_referencia"))
        )
        valores = v.verificar()
        validar_arquivos(anexos)
        tx.session.add(bm := SuperusBMMensal(centro_custo_id=centro_custo_id, **valores))
        _gravar_mes_unico(tx.session, valores["ano"], valores["mes_referencia"])
        tx.anexar(_pasta_mensal(bm.id), anexos, superus_bm_mensal_id=bm.id)
        return bm.id


def atualizar_bm_mensal(
    bm_id: int,
    dados: dict,
    novos_anexos: list[ArquivoNovo],
    remover_anexo_ids: list[int] | None = None,
    *,
    versao: int | None = None,
) -> None:
    """Edição de um BM existente. O centro de custo do registro não muda."""
    exigir_area_obras()
    remover_anexo_ids = remover_anexo_ids or []
    validar_arquivos(novos_anexos)
    with transacao("superus.atualizar_bm_mensal") as tx:
        bm = SuperusBMMensalRepository(tx.session).get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM não encontrado. Ele pode ter sido excluído; nada foi gravado.")
        exigir_centro(EMPRESA, bm.centro_custo_id, escrita=True)
        conferir_versao(bm, versao)
        v = _validar_mensal(dados, bm)
        v.valores["ano"] = ano_de_referencia(v.valores.get("mes_referencia"), bm)
        if (v.valores.get("mes_referencia"), v.valores["ano"]) != (bm.mes_referencia, bm.ano):
            _conferir_mes_livre(v, tx.session, bm.centro_custo_id, bm.id)
        # BMs importados do SIM antigo vieram sem anexo; para eles o anexo não é exigido na edição.
        if bm.id_legado is None and contar_anexos_finais(bm.anexos, remover_anexo_ids, novos_anexos) == 0:
            v.erro("anexos", "O BM precisa manter pelo menos um anexo.")
        # Valor, mês ou ano alterados: compara com o previsto atual. Senão, só mantém a justificativa já exigida
        # (BMs importados do SIM antigo têm o previsto do mês, mas nunca tiveram justificativa).
        ano, mes = v.valores.get("ano"), v.valores.get("mes_referencia")
        if (v.valores.get("valor_bm"), mes, ano) != (bm.valor_bm, bm.mes_referencia, bm.ano):
            previsto.conferir_variacao(v, previsto.previsto_de(tx.session, bm.centro_custo_id, ano, mes))
        elif bm.justificativa_variacao:
            previsto.conferir_variacao(v, bm.valor_previsto)
        else:
            v.valores[previsto.CAMPO_JUSTIFICATIVA] = None
        for k, val in v.verificar().items():
            setattr(bm, k, val)
        _gravar_mes_unico(tx.session, bm.ano, bm.mes_referencia)
        tx.remover_anexos(a for a in bm.anexos if a.id in set(remover_anexo_ids))
        tx.anexar(_pasta_mensal(bm.id), novos_anexos, superus_bm_mensal_id=bm.id)


def excluir_bm_mensal(bm_id: int, *, versao: int | None = None) -> None:
    exigir_area_obras()
    with transacao("superus.excluir_bm_mensal") as tx:
        repo = SuperusBMMensalRepository(tx.session)
        bm = repo.get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM não encontrado. Ele pode já ter sido excluído.")
        exigir_centro(EMPRESA, bm.centro_custo_id, escrita=True)
        conferir_versao(bm, versao)
        tx.marcar_para_remover(a.caminho_relativo for a in bm.anexos)
        repo.delete(bm)


# -------------------------------------------------------- BM Semanal ----


def _validar_semanal(dados: dict, atual: SuperusBMSemanal | None) -> Validador:
    v = Validador()
    v.texto("titulo", dados.get("titulo"), obrigatorio=True)
    v.escolha(
        "mes_referencia",
        dados.get("mes_referencia"),
        opcoes("superus.mes_referencia").com_valor_atual(atual and atual.mes_referencia),
        obrigatorio=True,
    )
    v.escolha(
        "semana", dados.get("semana"), opcoes("superus.semana").com_valor_atual(atual and atual.semana), obrigatorio=True
    )
    v.moeda("valor_bm", dados.get("valor_bm"), obrigatorio=True)
    return v


def listar_bms_semanais(*, centro_custo_id: int | None = None, mes: str | None = None, semana: str | None = None):
    permitidos = escopos_centros(EMPRESA)
    if centro_custo_id is not None:
        exigir_centro(EMPRESA, centro_custo_id)
    with leitura() as s:
        return SuperusBMSemanalRepository(s).listar(
            centro_custo_id=centro_custo_id,
            centro_custo_ids=permitidos,
            mes=mes,
            semana=semana,
        )


def obter_bm_semanal(bm_id: int) -> SuperusBMSemanal:
    with leitura() as s:
        bm = SuperusBMSemanalRepository(s).get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM semanal não encontrado. Ele pode ter sido excluído.")
        exigir_centro(EMPRESA, bm.centro_custo_id)
        return bm


def criar_bm_semanal(centro_custo_id: int, dados: dict, anexos: list[ArquivoNovo]) -> int:
    exigir_area_obras()
    exigir_centro(EMPRESA, centro_custo_id, escrita=True)
    v = _validar_semanal(dados, None)
    if not anexos:
        v.erro("anexos", "Adicione pelo menos um anexo.")
    valores = v.verificar()
    validar_arquivos(anexos)
    with transacao("superus.criar_bm_semanal") as tx:
        cc = SuperusCentroCustoRepository(tx.session).get(centro_custo_id)
        if cc is None:
            raise ValidationError({"centro_custo_id": "Centro de custo inexistente."})
        verificar_cc_ativo(cc)
        bm = SuperusBMSemanalRepository(tx.session).add(SuperusBMSemanal(centro_custo_id=centro_custo_id, **valores))
        tx.anexar(_pasta_semanal(bm.id), anexos, superus_bm_semanal_id=bm.id)
        return bm.id


def atualizar_bm_semanal(
    bm_id: int,
    dados: dict,
    novos_anexos: list[ArquivoNovo],
    remover_anexo_ids: list[int] | None = None,
    *,
    versao: int | None = None,
) -> None:
    exigir_area_obras()
    remover_anexo_ids = remover_anexo_ids or []
    validar_arquivos(novos_anexos)
    with transacao("superus.atualizar_bm_semanal") as tx:
        bm = SuperusBMSemanalRepository(tx.session).get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM semanal não encontrado. Ele pode ter sido excluído; nada foi gravado.")
        exigir_centro(EMPRESA, bm.centro_custo_id, escrita=True)
        conferir_versao(bm, versao)
        v = _validar_semanal(dados, bm)
        # BMs importados do SIM antigo vieram sem anexo; para eles o anexo não é exigido na edição.
        if bm.id_legado is None and contar_anexos_finais(bm.anexos, remover_anexo_ids, novos_anexos) == 0:
            v.erro("anexos", "O BM precisa manter pelo menos um anexo.")
        for k, val in v.verificar().items():
            setattr(bm, k, val)
        tx.remover_anexos(a for a in bm.anexos if a.id in set(remover_anexo_ids))
        tx.anexar(_pasta_semanal(bm.id), novos_anexos, superus_bm_semanal_id=bm.id)


def excluir_bm_semanal(bm_id: int, *, versao: int | None = None) -> None:
    exigir_area_obras()
    with transacao("superus.excluir_bm_semanal") as tx:
        repo = SuperusBMSemanalRepository(tx.session)
        bm = repo.get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM semanal não encontrado. Ele pode já ter sido excluído.")
        exigir_centro(EMPRESA, bm.centro_custo_id, escrita=True)
        conferir_versao(bm, versao)
        tx.marcar_para_remover(a.caminho_relativo for a in bm.anexos)
        repo.delete(bm)


# ------------------------------------------------ Faturamento (ADM) ----


def opcoes_filtro_faturamento() -> dict:
    exigir_area_adm()
    permitidos = escopos_centros(EMPRESA)
    with leitura() as s:
        distintos = SuperusBMMensalRepository(s).status_distintos(permitidos)
    configurados = list(opcoes("superus.status").valores)
    return {
        "centros": listar_centros_custo(),
        "status": configurados + [x for x in distintos if x not in configurados],
        "meses": list(opcoes("superus.mes_referencia").valores),
    }


def atualizar_faturamento(
    bm_id: int,
    *,
    status: object,
    valor_liberado: object,
    valor_emitido: object,
    mes_referencia: object,
    frs: object,
    po: object,
    novos_anexos: list[ArquivoNovo],
    remover_anexo_ids: list[int] | None = None,
    versao: int | None = None,
) -> None:
    """SIM SUPERUS ADM: Status, Valor Liberado, Valor Emitido, Mês, FRS, PO e Anexos.

    Valor Aprovado e Glosa não são alterados aqui (só consulta).
    """
    exigir_area_adm()
    remover_anexo_ids = remover_anexo_ids or []
    validar_arquivos(novos_anexos)
    with transacao("superus.atualizar_faturamento") as tx:
        bm = SuperusBMMensalRepository(tx.session).get_completo(bm_id)
        if bm is None:
            raise NotFoundError("BM não encontrado. Ele pode ter sido excluído; nada foi gravado.")
        exigir_centro(EMPRESA, bm.centro_custo_id, escrita=True)
        conferir_versao(bm, versao)
        v = Validador()
        v.escolha("status", status, opcoes("superus.status").com_valor_atual(bm.status), obrigatorio=True)
        v.moeda("valor_liberado", valor_liberado)
        v.moeda("valor_emitido", valor_emitido)
        _escolher_mes(v, mes_referencia, bm)
        v.numero("frs", frs)
        v.texto("po", po)
        if v.valores.get("mes_referencia") != bm.mes_referencia:
            v.valores["ano"] = ano_de_referencia(v.valores.get("mes_referencia"), bm)
            _conferir_mes_livre(v, tx.session, bm.centro_custo_id, bm.id)
        for k, val in v.verificar().items():
            setattr(bm, k, val)
        _gravar_mes_unico(tx.session, bm.ano, bm.mes_referencia)
        tx.remover_anexos(a for a in bm.anexos if a.id in set(remover_anexo_ids))
        tx.anexar(_pasta_mensal(bm.id), novos_anexos, superus_bm_mensal_id=bm.id)
