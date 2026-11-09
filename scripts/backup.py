"""Backup do banco SQLite local e da pasta de anexos.

Uso (na pasta do projeto):  .venv\\Scripts\\python scripts\\backup.py
Gera backups\\sim-backup-AAAAMMDD-HHMMSS.zip com o banco (cópia consistente,
mesmo com o SIM aberto) e todos os anexos.
Só funciona para o SQLite local; o banco corporativo terá o backup do TI.
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sim.config import BASE_DIR, load_settings  # noqa: E402


def main() -> Path:
    s = load_settings()
    if not s.is_sqlite:
        raise SystemExit("O backup por este script é só para o SQLite local.")
    db = Path(s.database_url.removeprefix("sqlite:///"))
    if not db.is_file():
        raise SystemExit(f"Banco não encontrado: {db}")
    destino_dir = BASE_DIR / "backups"
    destino_dir.mkdir(exist_ok=True)
    destino = destino_dir / f"sim-backup-{datetime.now():%Y%m%d-%H%M%S}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "sim.db"
        origem = sqlite3.connect(db)
        alvo = sqlite3.connect(copia)
        with alvo:
            origem.backup(alvo)  # API de backup do SQLite: cópia consistente
        origem.close()
        alvo.close()
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copia, "sim.db")
            if s.anexos_dir.exists():
                for f in s.anexos_dir.rglob("*"):
                    if f.is_file():
                        z.write(f, Path("anexos") / f.relative_to(s.anexos_dir))
    print(f"Backup criado: {destino}")
    return destino


if __name__ == "__main__":
    main()
