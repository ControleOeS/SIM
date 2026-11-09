"""Infraestrutura comum dos serviços: validação, transação e anexos."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from functools import lru_cache
from typing import Callable, Iterable, Iterator

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from sim.config import load_settings
from sim.database import session_scope
from sim.errors import ConflictError, PersistenceError, SimError, ValidationError
from sim.formatters import ValorInvalido, formatar_data_hora, ler_decimal
from sim.logging_setup import get_logger, nova_referencia
from sim.models import Anexo, utcnow
from sim.storage import ArquivoNovo, BancoStorage, LocalFileStorage

log = get_logger("services")

TEXT_MAX = 255
MSG_OBRIGATORIO = "Campo obrigatório."
MSG_NUMERO = "Informe um número válido (ex.: 1.234,56)."
MAX_MOEDA = Decimal("9999999999999.99")  # cabe em Numeric(15, 2)
MAX_NUMERO = Decimal("99999999999999.9999")  # cabe em Numeric(18, 4)
MSG_CONFLITO = (
    "Outra pessoa alterou ou excluiu este registro enquanto você editava. Nada foi gravado. "
    "Clique em Cancelar para carregar a versão atual e refaça a sua alteração."
)
MSG_OCUPADO = "O sistema está recebendo muitas gravações ao mesmo tempo. Nada foi salvo; tente de novo em instantes."


# ------------------------------------------------------ edição simultânea ----


def conferir_versao(registro, versao_lida: int | None) -> None:
    """Recusa a gravação se o registro mudou desde que o formulário foi aberto (bloqueio otimista).

    `versao_lida` é a versão que a tela mostrou (None = sem conferência, para uso interno e testes).
    O registro também é marcado como alterado, para que a gravação sempre confira a versão no banco,
    inclusive quando só os anexos mudam; isso fecha a janela entre esta leitura e o commit.
    """
    if versao_lida is not None and registro.versao != versao_lida:
        raise ConflictError(
            f"{MSG_CONFLITO} (última alteração em {formatar_data_hora(registro.atualizado_em)})"
        )
    registro.atualizado_em = utcnow()


# ----------------------------------------------------------- validação ----


class Validador:
    """Acumula erros por campo e devolve os valores já convertidos."""

    def __init__(self) -> None:
        self.erros: dict[str, str] = {}
        self.valores: dict[str, object] = {}

    def texto(self, campo: str, valor: object, *, obrigatorio: bool = False, max_len: int | None = TEXT_MAX):
        s = "" if valor is None else str(valor).strip()
        if obrigatorio and not s:
            self.erros[campo] = MSG_OBRIGATORIO
        elif max_len and len(s) > max_len:
            self.erros[campo] = f"Máximo de {max_len} caracteres."
        self.valores[campo] = s or None
        return self

    def _numero(self, campo, valor, obrigatorio, casas, maximo, nao_negativo):
        try:
            d = ler_decimal(valor)
        except ValorInvalido:
            self.erros[campo] = MSG_NUMERO
            self.valores[campo] = None
            return self
        if d is None:
            if obrigatorio:
                self.erros[campo] = MSG_OBRIGATORIO
        elif nao_negativo and d < 0:
            self.erros[campo] = "O valor não pode ser negativo."
        elif d.as_tuple().exponent < -casas:  # type: ignore[operator]
            self.erros[campo] = f"Use no máximo {casas} casas decimais."
        elif abs(d) > maximo:
            self.erros[campo] = "Valor acima do limite permitido."
        self.valores[campo] = d
        return self

    def moeda(self, campo: str, valor: object, *, obrigatorio: bool = False):
        return self._numero(campo, valor, obrigatorio, 2, MAX_MOEDA, nao_negativo=True)

    def numero(self, campo: str, valor: object, *, obrigatorio: bool = False):
        return self._numero(campo, valor, obrigatorio, 4, MAX_NUMERO, nao_negativo=True)

    def dia_do_mes(self, campo: str, valor: object, *, obrigatorio: bool = False):
        """Dia de 1 a 31 (início/fim de medição). Guardado como Decimal, como a coluna numérica."""
        s = "" if valor is None else str(valor).strip()
        if not s:
            if obrigatorio:
                self.erros[campo] = MSG_OBRIGATORIO
            self.valores[campo] = None
            return self
        try:
            d = ler_decimal(s)
        except ValorInvalido:
            d = None
        if d is None or d != d.to_integral_value() or not 1 <= d <= 31:
            self.erros[campo] = "Escolha um dia entre 1 e 31."
            self.valores[campo] = None
        else:
            self.valores[campo] = Decimal(int(d))
        return self

    def escolha(self, campo: str, valor: object, permitidos: Iterable[str], *, obrigatorio: bool = False):
        s = "" if valor is None else str(valor).strip()
        if not s:
            if obrigatorio:
                self.erros[campo] = MSG_OBRIGATORIO
        elif s not in set(permitidos):
            self.erros[campo] = "Opção não permitida."
        self.valores[campo] = s or None
        return self

    def erro(self, campo: str, mensagem: str):
        self.erros.setdefault(campo, mensagem)
        return self

    def verificar(self) -> dict[str, object]:
        if self.erros:
            raise ValidationError(dict(self.erros))
        return dict(self.valores)


# -------------------------------------------------------------- anexos ----


Storage = LocalFileStorage | BancoStorage


@lru_cache(maxsize=4)
def _storage_para(raiz: str) -> LocalFileStorage:
    return LocalFileStorage(raiz)


def get_storage() -> Storage:
    settings = load_settings()
    if settings.anexos_backend == "banco":
        return BancoStorage()
    if settings.anexos_backend != "disco":
        raise ValueError(f"SIM_ANEXOS_BACKEND inválido: {settings.anexos_backend!r} (use 'disco' ou 'banco').")
    return _storage_para(str(settings.anexos_dir))


def validar_arquivos(arquivos: list[ArquivoNovo]) -> None:
    limite = load_settings().max_anexo_mb * 1024 * 1024
    for a in arquivos:
        if not a.conteudo:
            raise ValidationError({"anexos": f"O arquivo '{a.nome}' está vazio."})
        if len(a.conteudo) > limite:
            raise ValidationError(
                {"anexos": f"O arquivo '{a.nome}' passa do limite de {load_settings().max_anexo_mb} MB."}
            )


class _Transacao:
    """Acompanha arquivos gravados/removidos para manter disco e banco coerentes.

    Com armazenamento transacional (BancoStorage), conteúdo e metadados seguem a mesma transação e
    não há nada a desfazer ou remover depois do commit.
    """

    def __init__(self, session: Session, storage: Storage):
        self.session = session
        self.storage = storage
        self._gravados: list[str] = []
        self._remover_apos_commit: list[str] = []

    def anexar(self, pasta: str, arquivos: list[ArquivoNovo], **dono: int) -> None:
        for arq in arquivos:
            if self.storage.transacional:
                g = self.storage.gravar(pasta, arq, self.session)
            else:
                g = self.storage.gravar(pasta, arq)
                self._gravados.append(g.caminho_relativo)
            self.session.add(
                Anexo(
                    nome_original=arq.nome[:255],
                    caminho_relativo=g.caminho_relativo,
                    tamanho_bytes=g.tamanho_bytes,
                    tipo_mime=g.tipo_mime,
                    sha256=g.sha256,
                    **dono,
                )
            )

    def remover_anexos(self, anexos: Iterable[Anexo]) -> None:
        for a in list(anexos):
            self.marcar_para_remover([a.caminho_relativo])
            self.session.delete(a)

    def marcar_para_remover(self, caminhos: Iterable[str]) -> None:
        if self.storage.transacional:
            for c in caminhos:
                self.storage.remover(c, self.session)
        else:
            self._remover_apos_commit.extend(caminhos)

    def desfazer(self) -> None:
        for c in self._gravados:
            try:
                self.storage.remover(c)
            except OSError:
                log.exception("Falha ao limpar anexo após erro: %s", c)

    def confirmar(self) -> None:
        for c in self._remover_apos_commit:
            try:
                self.storage.remover(c)
            except OSError:
                log.exception("Registro excluído, mas o arquivo não pôde ser removido: %s", c)


@contextmanager
def transacao(operacao: str, storage: Storage | None = None) -> Iterator[_Transacao]:
    """Executa uma gravação. Sucesso só é retornado depois do commit.

    Erros de domínio (SimError) passam como estão. Qualquer outro erro é
    registrado no log e convertido em PersistenceError com um código de referência,
    sem expor detalhes técnicos ao usuário.
    """
    storage = storage or get_storage()
    tx: _Transacao | None = None
    try:
        with session_scope() as session:
            tx = _Transacao(session, storage)
            yield tx
    except SimError:
        if tx:
            tx.desfazer()
        raise
    except StaleDataError as exc:  # alguém gravou a mesma linha entre a leitura e o commit
        if tx:
            tx.desfazer()
        log.info("Conflito de edição simultânea em %s: %s", operacao, exc)
        raise ConflictError(MSG_CONFLITO) from exc
    except IntegrityError as exc:
        if tx:
            tx.desfazer()
        ref = nova_referencia()
        log.exception("[%s] Violação de integridade em %s", ref, operacao)
        raise PersistenceError(
            "A gravação foi recusada pelo banco (registro relacionado inexistente ou duplicado). "
            f"Atualize a tela e tente de novo. Referência: {ref}",
            ref,
        ) from exc
    except OperationalError as exc:
        if tx:
            tx.desfazer()
        ref = nova_referencia()
        if banco_ocupado(exc):
            log.warning("[%s] Banco ocupado em %s: %s", ref, operacao, exc)
            raise PersistenceError(f"{MSG_OCUPADO} Referência: {ref}", ref) from exc
        log.exception("[%s] Erro técnico em %s", ref, operacao)
        raise PersistenceError(
            f"Não foi possível concluir a gravação. Nada foi salvo. Referência do erro: {ref}", ref
        ) from exc
    except Exception as exc:
        if tx:
            tx.desfazer()
        ref = nova_referencia()
        log.exception("[%s] Erro técnico em %s", ref, operacao)
        raise PersistenceError(
            f"Não foi possível concluir a gravação. Nada foi salvo. Referência do erro: {ref}", ref
        ) from exc
    else:
        tx.confirmar()


def banco_ocupado(exc: OperationalError) -> bool:
    """SQLite esgotou a espera por outra gravação (no PostgreSQL isso não acontece)."""
    texto = str(exc.orig).lower()
    return "locked" in texto or "busy" in texto


@contextmanager
def leitura() -> Iterator[Session]:
    """Sessão só para consultas."""
    try:
        with session_scope() as session:
            yield session
    except SimError:
        raise
    except Exception as exc:
        ref = nova_referencia()
        log.exception("[%s] Erro técnico em consulta", ref)
        raise PersistenceError(f"Não foi possível consultar os dados. Referência do erro: {ref}", ref) from exc


def verificar_anexo(anexo_id: int) -> Anexo:
    """Metadados do anexo, se o usuário pode acessar o BM dono e o arquivo existe. Não lê o conteúdo."""
    from sim.errors import NotFoundError
    from sim.auth import exigir_centro
    from sim.models import AsapBM, SuperusBMMensal, SuperusBMSemanal

    with leitura() as s:
        a = s.get(Anexo, anexo_id)
        if a is None:
            raise NotFoundError("Anexo não encontrado.")
        if a.asap_bm_id is not None:
            bm = s.get(AsapBM, a.asap_bm_id)
            if bm is None:
                raise NotFoundError("Anexo não encontrado.")
            exigir_centro("ASAP", bm.centro_custo_id)
        elif a.superus_bm_mensal_id is not None:
            bm = s.get(SuperusBMMensal, a.superus_bm_mensal_id)
            if bm is None:
                raise NotFoundError("Anexo não encontrado.")
            exigir_centro("SUPERUS", bm.centro_custo_id)
        elif a.superus_bm_semanal_id is not None:
            bm = s.get(SuperusBMSemanal, a.superus_bm_semanal_id)
            if bm is None:
                raise NotFoundError("Anexo não encontrado.")
            exigir_centro("SUPERUS", bm.centro_custo_id)
        else:
            raise NotFoundError("Anexo não encontrado.")
        s.expunge(a)
    if not get_storage().existe(a.caminho_relativo):
        raise NotFoundError(f"O arquivo '{a.nome_original}' não foi encontrado na pasta de anexos.")
    return a


def ler_anexo(anexo_id: int) -> tuple[Anexo, bytes]:
    a = verificar_anexo(anexo_id)
    return a, get_storage().ler(a.caminho_relativo)


def carregador_anexo(anexo_id: int) -> Callable[[], bytes]:
    """Função sem argumentos que lê o anexo só quando chamada (download sob demanda).

    O Streamlit executa o carregamento em outra thread, onde o usuário da sessão não está
    no contexto; por isso o usuário é capturado agora e a permissão é conferida de novo
    na hora da leitura. Sem usuário autenticado, falha aqui mesmo.
    """
    from sim.auth import principal_atual, usando_principal

    principal = principal_atual()

    def carregar() -> bytes:
        with usando_principal(principal):
            return ler_anexo(anexo_id)[1]

    return carregar


def contar_anexos_finais(existentes: Iterable[Anexo], remover_ids: Iterable[int], novos: list) -> int:
    remover = set(remover_ids)
    return sum(1 for a in existentes if a.id not in remover) + len(novos)
