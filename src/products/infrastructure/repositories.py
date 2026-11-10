from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from products.domain.entities import Product
from products.domain.repositories import ProductRepository
from products.infrastructure.models import ProductModel


def to_domain(model: ProductModel) -> Product:
    return Product(model.id, model.name, model.price, model.stock_quantity)


class SQLAlchemyProductRepository(ProductRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _conditions(q=None, stock=None, min_price=None, max_price=None):
        conditions = []
        if q is not None:
            # Escape SQL wildcards so % and _ are literal search characters.
            conditions.append(ProductModel.name.icontains(q, autoescape=True))
        if stock == "in_stock":
            conditions.append(ProductModel.stock_quantity > 0)
        elif stock == "sold_out":
            conditions.append(ProductModel.stock_quantity == 0)
        if min_price is not None:
            conditions.append(ProductModel.price >= min_price)
        if max_price is not None:
            conditions.append(ProductModel.price <= max_price)
        return conditions

    async def list(self, offset: int, limit: int, *, q=None, stock=None,
                   min_price=None, max_price=None, sort="id") -> list[Product]:
        sort_columns = {"id": ProductModel.id, "price": ProductModel.price, "name": ProductModel.name}
        query = (select(ProductModel).where(*self._conditions(q, stock, min_price, max_price))
                 .order_by(sort_columns[sort], ProductModel.id).offset(offset).limit(limit))
        rows = await self.session.scalars(query)
        return [to_domain(row) for row in rows]

    async def count(self, *, q=None, stock=None, min_price=None, max_price=None) -> int:
        query = select(func.count()).select_from(ProductModel).where(*self._conditions(q, stock, min_price, max_price))
        return await self.session.scalar(query)

    async def find_by_id(self, product_id: int, *, for_update: bool = False) -> Product | None:
        query = select(ProductModel).where(ProductModel.id == product_id)
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(query)
        return to_domain(row) if row is not None else None

    async def get_many_for_update(self, product_ids: list[int]) -> list[Product]:
        # Every stock-changing operation locks products in the same order.
        query = (select(ProductModel).where(ProductModel.id.in_(product_ids))
                 .order_by(ProductModel.id).with_for_update()
                 .execution_options(populate_existing=True))
        rows = await self.session.scalars(query)
        return [to_domain(row) for row in rows]

    async def save(self, product: Product) -> Product:
        if product.id is None:
            row = ProductModel(name=product.name, price=product.price, stock_quantity=product.stock_quantity)
            self.session.add(row)
        else:
            row = await self.session.get(ProductModel, product.id)
            if row is None:
                from shared.core.exceptions import NotFoundException
                raise NotFoundException("Product not found.")
            row.name = product.name
            row.price = product.price
            row.stock_quantity = product.stock_quantity
        await self.session.flush()
        return to_domain(row)
