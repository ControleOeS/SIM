from __future__ import annotations

from typing import Generic, Sequence, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from sim.models import Base, Empresa

M = TypeVar("M", bound=Base)


class Repository(Generic[M]):
    model: type[M]

    def __init__(self, session: Session):
        self.session = session

    def get(self, id_: int) -> M | None:
        return self.session.get(self.model, id_)

    def add(self, obj: M) -> M:
        self.session.add(obj)
        self.session.flush()  # obtém o ID sem confirmar a transação
        return obj

    def delete(self, obj: M) -> None:
        self.session.delete(obj)
        self.session.flush()

    def count(self) -> int:
        from sqlalchemy import func

        return self.session.scalar(select(func.count()).select_from(self.model)) or 0


class EmpresaRepository(Repository[Empresa]):
    model = Empresa

    def por_codigo(self, codigo: str) -> Empresa | None:
        return self.session.scalar(select(Empresa).where(Empresa.codigo == codigo))

    def listar(self) -> Sequence[Empresa]:
        return self.session.scalars(select(Empresa).order_by(Empresa.nome)).all()
