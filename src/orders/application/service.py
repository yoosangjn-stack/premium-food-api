from shared.domain.transaction import TransactionManager

from uuid import UUID

from orders.domain.entities import Order, OrderItem
from orders.domain.repositories import OrderRepository
from products.domain.repositories import ProductRepository
from shared.core.exceptions import ForbiddenException, NotFoundException, ValidationException


class OrderService:
    def __init__(self, orders: OrderRepository, products: ProductRepository, transaction: TransactionManager):
        self.orders = orders
        self.products = products
        self.transaction = transaction

    async def create_order(self, user_id: UUID, items: list[dict]) -> Order:
        try:
            if not 1 <= len(items) <= 20:
                raise ValidationException("An order must contain 1 to 20 items.")
            product_ids = [item["product_id"] for item in items]
            if any(type(value) is not int or value < 1 for value in product_ids):
                raise ValidationException("Product IDs must be positive integers.")
            if len(set(product_ids)) != len(product_ids):
                raise ValidationException("Duplicate product IDs are not allowed.")
            products = await self.products.get_many_for_update(sorted(product_ids))
            by_id = {product.id: product for product in products}
            if len(by_id) != len(product_ids):
                raise NotFoundException("One or more products were not found.")
            order_items = []
            # Validate every line before saving any stock changes.
            for item in items:
                product = by_id[item["product_id"]]
                order_item = OrderItem(product.id, product.name, item["quantity"], product.price)
                product.reduce_stock(order_item.quantity)
                order_items.append(order_item)
            order = Order(user_id=user_id, items=order_items)
            for product in products:
                await self.products.save(product)
            result = await self.orders.add(order)
            await self.transaction.commit()
            return result
        except Exception:
            await self.transaction.rollback()
            raise

    async def list_orders(self, user_id: UUID, offset: int = 0, limit: int = 20) -> list[Order]:
        return await self.orders.list_by_user(user_id, offset, limit)

    async def get_order(self, order_id: UUID, user_id: UUID, role: str = "USER") -> Order:
        order = await self.orders.find_by_id(order_id)
        if order is None:
            raise NotFoundException("Order not found.")
        self._check_access(order, user_id, role)
        return order

    async def cancel_order(self, order_id: UUID, user_id: UUID, role: str = "USER") -> Order:
        try:
            # The order lock serializes cancellation; product locks match create_order.
            order = await self.orders.find_by_id(order_id, for_update=True)
            if order is None:
                raise NotFoundException("Order not found.")
            self._check_access(order, user_id, role)
            order.cancel()
            products = await self.products.get_many_for_update(sorted(item.product_id for item in order.items))
            by_id = {product.id: product for product in products}
            if len(by_id) != len(order.items):
                raise NotFoundException("An ordered product was not found.")
            for item in order.items:
                by_id[item.product_id].restore_stock(item.quantity)
            for product in products:
                await self.products.save(product)
            result = await self.orders.save_status(order)
            await self.transaction.commit()
            return result
        except Exception:
            await self.transaction.rollback()
            raise

    @staticmethod
    def _check_access(order: Order, user_id: UUID, role: str):
        if order.user_id != user_id and role != "ADMIN":
            raise ForbiddenException("You cannot access another user's order.")
