"""Armazenamento do conteúdo dos anexos. Os metadados ficam sempre na tabela `anexos`.

Duas implementações, escolhidas por SIM_ANEXOS_BACKEND (ver services.common.get_storage):

- `LocalFileStorage` ("disco", padrão): arquivos em SIM_ANEXOS_DIR (data/anexos), por tipo de registro e ID.
  Gravados antes do commit e desfeitos/removidos pela transação do serviço.
- `BancoStorage` ("banco"): conteúdo na tabela `anexos_conteudo`, dentro da mesma transação do serviço.
  Usado na hospedagem gratuita (Streamlit Community Cloud), cujo disco é apagado a cada reinício.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArquivoNovo:
    """Arquivo enviado pelo usuário, ainda não gravado."""

    nome: str
    conteudo: bytes
    tipo_mime: str | None = None


@dataclass(frozen=True)
class ArquivoGravado:
    caminho_relativo: str
    tamanho_bytes: int
    sha256: str
    tipo_mime: str | None


def nome_seguro(nome: str) -> str:
    base = Path(nome).name  # descarta qualquer diretório enviado no nome
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "arquivo"
    return base[:120]


def _novo_caminho(pasta: str, arquivo: ArquivoNovo) -> str:
    return f"{pasta}/{uuid.uuid4().hex}_{nome_seguro(arquivo.nome)}"


def _metadados(relativo: str, arquivo: ArquivoNovo) -> ArquivoGravado:
    return ArquivoGravado(
        caminho_relativo=relativo,
        tamanho_bytes=len(arquivo.conteudo),
        sha256=hashlib.sha256(arquivo.conteudo).hexdigest(),
        tipo_mime=arquivo.tipo_mime or mimetypes.guess_type(arquivo.nome)[0],
    )


class LocalFileStorage:
    def __init__(self, raiz: Path):
        self.raiz = Path(raiz).resolve()

    def _resolver(self, caminho_relativo: str) -> Path:
        destino = (self.raiz / caminho_relativo).resolve()
        if self.raiz not in destino.parents:
            raise ValueError("Caminho de anexo fora da pasta de anexos.")
        return destino

    # Grava fora da transação do banco: a transação do serviço desfaz/remove depois.
    transacional = False

    def gravar(self, pasta: str, arquivo: ArquivoNovo) -> ArquivoGravado:
        relativo = _novo_caminho(pasta, arquivo)
        destino = self._resolver(relativo)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "xb") as f:
            f.write(arquivo.conteudo)
        return _metadados(relativo, arquivo)

    def ler(self, caminho_relativo: str) -> bytes:
        return self._resolver(caminho_relativo).read_bytes()

    def existe(self, caminho_relativo: str) -> bool:
        return self._resolver(caminho_relativo).is_file()

    def remover(self, caminho_relativo: str) -> None:
        destino = self._resolver(caminho_relativo)
        if destino.exists():
            destino.unlink()
        # remove pastas vazias do registro
        pasta = destino.parent
        while pasta != self.raiz and pasta.exists() and not any(pasta.iterdir()):
            pasta.rmdir()
            pasta = pasta.parent


class BancoStorage:
    """Conteúdo dos anexos na tabela `anexos_conteudo`, chaveado pelo mesmo caminho relativo.

    `gravar` e `remover` usam a sessão da transação do serviço: o arquivo só existe se o BM for
    gravado, sem limpeza posterior. `ler`/`existe` abrem uma leitura própria.
    """

    transacional = True

    def gravar(self, pasta: str, arquivo: ArquivoNovo, session) -> ArquivoGravado:
        from sim.models import AnexoConteudo

        relativo = _novo_caminho(pasta, arquivo)
        session.add(AnexoConteudo(caminho_relativo=relativo, conteudo=arquivo.conteudo))
        return _metadados(relativo, arquivo)

    def remover(self, caminho_relativo: str, session) -> None:
        from sqlalchemy import delete

        from sim.models import AnexoConteudo

        session.execute(delete(AnexoConteudo).where(AnexoConteudo.caminho_relativo == caminho_relativo))

    def ler(self, caminho_relativo: str) -> bytes:
        from sim.database import session_scope
        from sim.models import AnexoConteudo

        with session_scope() as session:
            registro = session.get(AnexoConteudo, caminho_relativo)
            if registro is None:
                raise FileNotFoundError(caminho_relativo)
            return registro.conteudo

    def existe(self, caminho_relativo: str) -> bool:
        from sqlalchemy import select

        from sim.database import session_scope
        from sim.models import AnexoConteudo

        with session_scope() as session:
            return session.scalar(
                select(AnexoConteudo.caminho_relativo).where(AnexoConteudo.caminho_relativo == caminho_relativo)
            ) is not None
