"""Migrações sobre um banco com dados não podem apagar registros ligados por chave estrangeira.

No SQLite, alterar uma tabela recria a tabela; com foreign_keys ligado isso disparava ON DELETE
CASCADE (grants apagados) ou RESTRICT (migração falhava com BMs). Ver migrations/env.py.
"""
from __future__ import annotations

import sqlite3

from alembic import command

from sim.bootstrap import alembic_config


def test_migracao_0007_preserva_dados_relacionados(tmp_path):
    caminho = tmp_path / "com_dados.db"
    url = f"sqlite:///{caminho.as_posix()}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "0006")

    con = sqlite3.connect(caminho)
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(
        """
        INSERT INTO usuarios (id, email, email_normalizado, nome, senha_hash, perfil, ativo, deve_trocar_senha,
                              tentativas_login, versao_sessao, criado_em, atualizado_em)
            VALUES (1, 'a@e.test', 'a@e.test', 'A', 'x', 'usuario', 1, 0, 0, 1, '2026-01-01', '2026-01-01');
        INSERT INTO superus_centros_custo (id, empresa_id, titulo, titulo_chave, obra_cliente, gestor_obra, coligada,
                              inicio_medicao, fim_medicao, criado_em, atualizado_em)
            VALUES (1, (SELECT id FROM empresas WHERE codigo='SUPERUS'), 'CC', 'cc', 'Obra', 'G', 'SUPERUS ENGENHARIA',
                    1, 31, '2026-01-01', '2026-01-01');
        INSERT INTO asap_centros_custo (id, empresa_id, titulo, titulo_chave, cliente, inicio_medicao, fim_medicao,
                              email, criado_em, atualizado_em)
            VALUES (1, (SELECT id FROM empresas WHERE codigo='ASAP'), 'A1', 'a1', 'Cli', 1, 31, 'x@e.test',
                    '2026-01-01', '2026-01-01');
        INSERT INTO superus_bms_mensais (id, centro_custo_id, titulo, numero_contrato, cidade, mes_referencia, tipo,
                              ano, status, valor_bm, criado_em, atualizado_em)
            VALUES (1, 1, 'BM', '55/2026', 'Belém', 'Março', 'BM', '2026', 'BM em Análise do Cliente', 10,
                    '2026-01-01', '2026-01-01');
        INSERT INTO acessos_centros_custo (usuario_id, empresa_id, superus_centro_custo_id, criado_em)
            VALUES (1, (SELECT id FROM empresas WHERE codigo='SUPERUS'), 1, '2026-01-01');
        INSERT INTO acessos_centros_custo (usuario_id, empresa_id, asap_centro_custo_id, criado_em)
            VALUES (1, (SELECT id FROM empresas WHERE codigo='ASAP'), 1, '2026-01-01');
        """
    )
    con.commit()
    con.close()

    command.upgrade(cfg, "head")

    con = sqlite3.connect(caminho)
    contagem = {
        t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("superus_centros_custo", "asap_centros_custo", "superus_bms_mensais", "acessos_centros_custo")
    }
    assert contagem == {
        "superus_centros_custo": 1, "asap_centros_custo": 1, "superus_bms_mensais": 1, "acessos_centros_custo": 2,
    }
    assert con.execute("SELECT ativo FROM superus_centros_custo").fetchone() == (1,)
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert not con.execute("SELECT name FROM sqlite_master WHERE name LIKE '_alembic_tmp%'").fetchall()
    con.close()
