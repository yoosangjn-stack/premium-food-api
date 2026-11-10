from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from orders.domain.entities import Order


class OrderRepository(ABC):
    @abstractmethod
    async def add(self, order: Order) -> Order: ...

    @abstractmethod
    async def find_by_id(self, order_id: UUID, *, for_update: bool = False) -> Order | None: ...

    @abstractmethod
    async def list_by_user(self, user_id: UUID, offset: int, limit: int) -> list[Order]: ...

    @abstractmethod
    async def save_status(self, order: Order) -> Order: ...
