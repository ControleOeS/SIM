"""Copia o SIM local (SQLite + pasta de anexos) para o banco da hospedagem (PostgreSQL/Neon).

Mantém todos os registros com os mesmos IDs: usuários, senhas (hash), permissões, auditoria, CCs, BMs etc.
Os arquivos de data/anexos vão para a tabela `anexos_conteudo` (SIM_ANEXOS_BACKEND=banco).

Uso (o endereço do banco de destino NUNCA é impresso):
    1. Grave o endereço do Neon no arquivo .env.hospedagem (ignorado pelo Git), numa linha:
           DATABASE_URL=postgresql://usuario:senha@ep-xxxx.../neondb?sslmode=require
    2. .venv\\Scripts\\python.exe -m scripts.migrar_para_hospedagem              # simula e confere
       .venv\\Scripts\\python.exe -m scripts.migrar_para_hospedagem --aplicar    # grava no destino

Regras de segurança:
- O destino precisa estar vazio (só o esquema). Se já houver dados lá, nada é gravado.
- Tudo é gravado numa única transação: ou copia tudo, ou nada.
- O SIM local não é alterado. Feche o INICIAR_SIM.bat antes, para nada mudar durante a cópia.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, func, insert, select, text

from sim.bootstrap import migrar
from sim.config import BASE_DIR, normalizar_url_banco
from sim.models import Base

ARQUIVO_DESTINO = BASE_DIR / ".env.hospedagem"
IGNORAR = {"alembic_version"}
# Tabelas que as próprias migrações preenchem (0002: ASAP e SUPERUS). Aceitas no destino se iguais às locais.
SEMEADAS = {"empresas"}


def _url_destino(arquivo: Path) -> str:
    if not arquivo.is_file():
        raise SystemExit(f"Crie o arquivo {arquivo.name} com a linha DATABASE_URL=... (veja o topo deste script).")
    for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
        chave, _, valor = linha.partition("=")
        if chave.strip() == "DATABASE_URL":
            url = valor.strip().strip('"').strip("'")
            if not url.startswith(("postgresql://", "postgres://")):
                raise SystemExit("DATABASE_URL do destino deve começar com postgresql://")
            host = url.split("@", 1)[-1].split("/", 1)[0]
            if not host or host.startswith(".") or "@" not in url:
                raise SystemExit("DATABASE_URL incompleto: o servidor depois do '@' deve começar com 'ep-'.")
            return normalizar_url_banco(url)
    raise SystemExit(f"Linha DATABASE_URL não encontrada em {arquivo.name}.")


def _contagens(conn, tabelas) -> dict[str, int]:
    return {t.name: conn.execute(select(func.count()).select_from(t)).scalar_one() for t in tabelas}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aplicar", action="store_true", help="grava no destino (sem isso, só simula)")
    parser.add_argument("--origem", default=str(BASE_DIR / "data" / "sim.db"))
    parser.add_argument("--anexos", default=str(BASE_DIR / "data" / "anexos"))
    parser.add_argument("--destino-arquivo", default=str(ARQUIVO_DESTINO))
    parser.add_argument("--destino-url", help=argparse.SUPPRESS)  # testes
    args = parser.parse_args(argv)

    origem_db = Path(args.origem)
    if not origem_db.is_file():
        raise SystemExit(f"Banco local não encontrado: {origem_db}")
    origem = create_engine(f"sqlite:///{origem_db.as_posix()}")
    destino_url = args.destino_url or _url_destino(Path(args.destino_arquivo))
    destino = create_engine(destino_url)
    tabelas = [t for t in Base.metadata.sorted_tables if t.name not in IGNORAR]
    raiz_anexos = Path(args.anexos).resolve()

    # 1. Origem: versão do esquema e tabelas cobertas.
    with origem.connect() as conn:
        versao_origem = conn.execute(text("select version_num from alembic_version")).scalar()
        existentes = {r[0] for r in conn.execute(text("select name from sqlite_master where type='table'"))}
        sem_modelo = existentes - {t.name for t in tabelas} - IGNORAR - {"sqlite_sequence"}
        if sem_modelo:
            raise SystemExit(f"Tabelas locais sem modelo (não seriam copiadas): {sorted(sem_modelo)}")
        qtd_origem = _contagens(conn, tabelas)
        caminhos = [r[0] for r in conn.execute(text("select caminho_relativo from anexos"))]
        ja_no_banco = {r[0] for r in conn.execute(text("select caminho_relativo from anexos_conteudo"))}

    faltando = []
    arquivos: dict[str, Path] = {}
    for rel in caminhos:
        if rel in ja_no_banco:
            continue
        caminho = (raiz_anexos / rel).resolve()
        if raiz_anexos not in caminho.parents or not caminho.is_file():
            faltando.append(rel)
        else:
            arquivos[rel] = caminho

    print(f"Origem: {origem_db} (esquema {versao_origem})")
    for nome, qtd in qtd_origem.items():
        print(f"  {nome:28} {qtd:6}")
    print(f"  arquivos de anexo a enviar   {len(arquivos):6}  "
          f"({sum(p.stat().st_size for p in arquivos.values()) / 1e6:.1f} MB)")
    if faltando:
        print(f"ATENÇÃO: {len(faltando)} anexo(s) registrados sem arquivo no disco: {faltando}")

    # 2. Destino: esquema na versão atual e vazio.
    print("Destino: preparando o esquema…")
    migrar(destino_url)
    with destino.connect() as conn:
        versao_destino = conn.execute(text("select version_num from alembic_version")).scalar()
        if versao_destino != versao_origem:
            raise SystemExit(f"Versões diferentes: local {versao_origem}, destino {versao_destino}. "
                             "Abra o SIM local uma vez para atualizar o esquema e tente de novo.")
        ocupadas = {n: q for n, q in _contagens(conn, tabelas).items() if q and n not in SEMEADAS}
        semeadas = {}
        for t in tabelas:
            if t.name in SEMEADAS:
                no_destino = {tuple(r) for r in conn.execute(select(t))}
                with origem.connect() as src:
                    locais = {tuple(r) for r in src.execute(select(t))}
                if not no_destino <= locais:
                    raise SystemExit(f"A tabela {t.name} do destino difere da local. Nada foi gravado.")
                semeadas[t.name] = no_destino
    if ocupadas:
        raise SystemExit(f"O destino já tem dados {ocupadas}. Nada foi gravado. "
                         "Use um banco vazio (no Neon: Branches → criar ou Reset) para copiar.")
    print(f"Destino: vazio, esquema {versao_destino}.")

    if not args.aplicar:
        print("\nSimulação concluída. Para gravar, rode de novo com --aplicar.")
        return

    # 3. Cópia em uma transação.
    with origem.connect() as src, destino.begin() as dst:
        for t in tabelas:
            ja_existem = semeadas.get(t.name, set())
            linhas = [dict(r._mapping) for r in src.execute(select(t).order_by(*t.primary_key.columns))
                      if tuple(r) not in ja_existem]
            if linhas:
                dst.execute(insert(t), linhas)
        conteudo = Base.metadata.tables["anexos_conteudo"]
        for rel, caminho in arquivos.items():
            dst.execute(insert(conteudo).values(caminho_relativo=rel, conteudo=caminho.read_bytes(),
                                                 criado_em=func.now()))
        # IDs copiados: o próximo registro novo continua a partir do maior ID.
        if dst.dialect.name == "postgresql":
            for t in tabelas:
                pk = list(t.primary_key.columns)
                if len(pk) == 1 and pk[0].type.python_type is int:
                    dst.execute(text(
                        f"select setval(pg_get_serial_sequence('{t.name}', '{pk[0].name}'), "
                        f"coalesce(max({pk[0].name}), 1), max({pk[0].name}) is not null) from {t.name}"
                    ))
        qtd_destino = _contagens(dst, tabelas)

    esperado = dict(qtd_origem)
    esperado["anexos_conteudo"] += len(arquivos)
    diferencas = {n: (esperado[n], qtd_destino[n]) for n in esperado if esperado[n] != qtd_destino[n]}
    if diferencas:
        print(f"ERRO: contagens diferentes (local, destino): {diferencas}")
        sys.exit(1)
    print("\nCópia concluída: todas as contagens conferem.")


if __name__ == "__main__":
    main()
