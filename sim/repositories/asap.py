from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from sim.models import AsapBM, AsapCentroCusto
from sim.repositories.base import Repository


class AsapCentroCustoRepository(Repository[AsapCentroCusto]):
    model = AsapCentroCusto

    def listar(self) -> Sequence[AsapCentroCusto]:
        # Sort('Lista de Apoio ASAP', Título, Ascending)
        return self.session.scalars(select(AsapCentroCusto).order_by(AsapCentroCusto.titulo)).all()

    def por_chave(self, titulo_chave: str) -> AsapCentroCusto | None:
        return self.session.scalar(select(AsapCentroCusto).where(AsapCentroCusto.titulo_chave == titulo_chave))

    def possui_bms(self, cc_id: int) -> bool:
        return self.session.scalar(select(AsapBM.id).where(AsapBM.centro_custo_id == cc_id).limit(1)) is not None


class AsapBMRepository(Repository[AsapBM]):
    model = AsapBM

    def get_completo(self, id_: int) -> AsapBM | None:
        return self.session.scalar(
            select(AsapBM)
            .options(joinedload(AsapBM.centro_custo), selectinload(AsapBM.anexos))
            .where(AsapBM.id == id_)
        )

    def listar(
        self,
        *,
        centro_custo_id: int | None = None,
        centro_custo_ids: set[int] | None = None,
        mes: str | None = None,
        status: str | None = None,
    ) -> Sequence[AsapBM]:
        """BMs ordenados por ID decrescente, com filtros opcionais (combinados por E)."""
        if centro_custo_ids is not None and not centro_custo_ids:
            return []
        q = select(AsapBM).options(joinedload(AsapBM.centro_custo), selectinload(AsapBM.anexos))
        if centro_custo_id is not None:
            q = q.where(AsapBM.centro_custo_id == centro_custo_id)
        if centro_custo_ids is not None:
            q = q.where(AsapBM.centro_custo_id.in_(centro_custo_ids))
        if mes:
            q = q.where(AsapBM.mes_referencia == mes)
        if status:
            q = q.where(AsapBM.status == status)
        return self.session.scalars(q.order_by(AsapBM.id.desc())).unique().all()

    def status_distintos(self, centro_custo_ids: set[int] | None = None) -> list[str]:
        # Distinct('BMs ASAP', Status.Value)
        q = select(AsapBM.status).distinct().order_by(AsapBM.status)
        if centro_custo_ids is not None:
            if not centro_custo_ids:
                return []
            q = q.where(AsapBM.centro_custo_id.in_(centro_custo_ids))
        return list(self.session.scalars(q))

    def centros_com_bm(self, centro_custo_ids: set[int] | None = None) -> Sequence[AsapCentroCusto]:
        # Distinct('BMs ASAP', 'Centro de Custo'.Value), mas pelo ID estável
        q = (
            select(AsapCentroCusto)
            .where(AsapCentroCusto.id.in_(select(AsapBM.centro_custo_id)))
            .order_by(AsapCentroCusto.titulo)
        )
        if centro_custo_ids is not None:
            if not centro_custo_ids:
                return []
            q = q.where(AsapCentroCusto.id.in_(centro_custo_ids))
        return self.session.scalars(q).all()
