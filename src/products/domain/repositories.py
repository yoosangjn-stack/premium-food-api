from __future__ import annotations

from abc import ABC, abstractmethod

from products.domain.entities import Product


class ProductRepository(ABC):
    @abstractmethod
    async def list(self, offset: int, limit: int, *, q: str | None = None, stock: str | None = None,
                   min_price: int | None = None, max_price: int | None = None, sort: str = "id") -> list[Product]: ...

    @abstractmethod
    async def count(self, *, q: str | None = None, stock: str | None = None,
                    min_price: int | None = None, max_price: int | None = None) -> int: ...

    @abstractmethod
    async def find_by_id(self, product_id: int, *, for_update: bool = False) -> Product | None: ...

    @abstractmethod
    async def get_many_for_update(self, product_ids: list[int]) -> list[Product]: ...

    @abstractmethod
    async def save(self, product: Product) -> Product: ...
