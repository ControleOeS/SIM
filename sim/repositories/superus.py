from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from sim.models import SuperusBMMensal, SuperusBMSemanal, SuperusCentroCusto
from sim.repositories.base import Repository


class SuperusCentroCustoRepository(Repository[SuperusCentroCusto]):
    model = SuperusCentroCusto

    def listar(self) -> Sequence[SuperusCentroCusto]:
        # Sort('Lista de Apoio', Título, SortOrder.Ascending)
        return self.session.scalars(select(SuperusCentroCusto).order_by(SuperusCentroCusto.titulo)).all()

    def por_chave(self, titulo_chave: str) -> SuperusCentroCusto | None:
        return self.session.scalar(
            select(SuperusCentroCusto).where(SuperusCentroCusto.titulo_chave == titulo_chave)
        )

    def possui_bms(self, cc_id: int) -> bool:
        mensal = select(SuperusBMMensal.id).where(SuperusBMMensal.centro_custo_id == cc_id).limit(1)
        semanal = select(SuperusBMSemanal.id).where(SuperusBMSemanal.centro_custo_id == cc_id).limit(1)
        return self.session.scalar(mensal) is not None or self.session.scalar(semanal) is not None


class SuperusBMMensalRepository(Repository[SuperusBMMensal]):
    model = SuperusBMMensal

    def get_completo(self, id_: int) -> SuperusBMMensal | None:
        return self.session.scalar(
            select(SuperusBMMensal)
            .options(
                joinedload(SuperusBMMensal.centro_custo),
                selectinload(SuperusBMMensal.anexos),
                selectinload(SuperusBMMensal.itens),
            )
            .where(SuperusBMMensal.id == id_)
        )

    def listar(
        self,
        *,
        centro_custo_id: int | None = None,
        centro_custo_ids: set[int] | None = None,
        mes: str | None = None,
        status: str | None = None,
        po: str | None = None,
    ) -> Sequence[SuperusBMMensal]:
        if centro_custo_ids is not None and not centro_custo_ids:
            return []
        q = select(SuperusBMMensal).options(
            joinedload(SuperusBMMensal.centro_custo), selectinload(SuperusBMMensal.anexos)
        )
        if centro_custo_id is not None:
            q = q.where(SuperusBMMensal.centro_custo_id == centro_custo_id)
        if centro_custo_ids is not None:
            q = q.where(SuperusBMMensal.centro_custo_id.in_(centro_custo_ids))
        if mes:
            q = q.where(SuperusBMMensal.mes_referencia == mes)
        if status:
            q = q.where(SuperusBMMensal.status == status)
        if po and po.strip():
            # varPO in PO: trecho do texto, sem diferenciar maiúsculas
            q = q.where(SuperusBMMensal.po.icontains(po.strip(), autoescape=True))
        return self.session.scalars(q.order_by(SuperusBMMensal.id.desc())).unique().all()

    def status_distintos(self, centro_custo_ids: set[int] | None = None) -> list[str]:
        q = select(SuperusBMMensal.status).distinct().order_by(SuperusBMMensal.status)
        if centro_custo_ids is not None:
            if not centro_custo_ids:
                return []
            q = q.where(SuperusBMMensal.centro_custo_id.in_(centro_custo_ids))
        return list(self.session.scalars(q))


class SuperusBMSemanalRepository(Repository[SuperusBMSemanal]):
    model = SuperusBMSemanal

    def get_completo(self, id_: int) -> SuperusBMSemanal | None:
        return self.session.scalar(
            select(SuperusBMSemanal)
            .options(joinedload(SuperusBMSemanal.centro_custo), selectinload(SuperusBMSemanal.anexos))
            .where(SuperusBMSemanal.id == id_)
        )

    def listar(
        self,
        *,
        centro_custo_id: int | None = None,
        centro_custo_ids: set[int] | None = None,
        mes: str | None = None,
        semana: str | None = None,
    ) -> Sequence[SuperusBMSemanal]:
        if centro_custo_ids is not None and not centro_custo_ids:
            return []
        q = select(SuperusBMSemanal).options(
            joinedload(SuperusBMSemanal.centro_custo), selectinload(SuperusBMSemanal.anexos)
        )
        if centro_custo_id is not None:
            q = q.where(SuperusBMSemanal.centro_custo_id == centro_custo_id)
        if centro_custo_ids is not None:
            q = q.where(SuperusBMSemanal.centro_custo_id.in_(centro_custo_ids))
        if mes:
            q = q.where(SuperusBMSemanal.mes_referencia == mes)
        if semana:
            q = q.where(SuperusBMSemanal.semana == semana)
        return self.session.scalars(q.order_by(SuperusBMSemanal.id.desc())).unique().all()
