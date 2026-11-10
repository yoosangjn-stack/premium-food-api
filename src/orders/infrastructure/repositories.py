from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from orders.domain.entities import Order, OrderItem, OrderStatus
from orders.domain.repositories import OrderRepository
from orders.infrastructure.models import OrderItemModel, OrderModel


def to_domain(row: OrderModel) -> Order:
    return Order(user_id=row.user_id,
                 items=[OrderItem(item.product_id, item.product_name, item.quantity, item.unit_price)
                        for item in sorted(row.items, key=lambda item: item.id)],
                 id=row.id, order_number=row.order_number, ordered_at=row.ordered_at,
                 status=OrderStatus(row.status))


class SQLAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, order: Order) -> Order:
        row = OrderModel(id=order.id, order_number=order.order_number, user_id=order.user_id,
                         ordered_at=order.ordered_at, status=order.status.value, total_price=order.total_price,
                         items=[OrderItemModel(product_id=item.product_id, product_name=item.product_name,
                                               quantity=item.quantity, unit_price=item.unit_price,
                                               total_price=item.total_price) for item in order.items])
        self.session.add(row)
        await self.session.flush()
        return to_domain(row)

    async def find_by_id(self, order_id: UUID, *, for_update: bool = False) -> Order | None:
        query = select(OrderModel).where(OrderModel.id == order_id).options(selectinload(OrderModel.items))
        if for_update:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(query)
        return to_domain(row) if row is not None else None

    async def list_by_user(self, user_id: UUID, offset: int, limit: int) -> list[Order]:
        query = (select(OrderModel).where(OrderModel.user_id == user_id)
                 .options(selectinload(OrderModel.items))
                 .order_by(OrderModel.ordered_at.desc(), OrderModel.id.desc()).offset(offset).limit(limit))
        rows = await self.session.scalars(query)
        return [to_domain(row) for row in rows]

    async def save_status(self, order: Order) -> Order:
        row = await self.session.get(OrderModel, order.id)
        if row is None:
            from shared.core.exceptions import NotFoundException
            raise NotFoundException("Order not found.")
        row.status = order.status.value
        await self.session.flush()
        return order
