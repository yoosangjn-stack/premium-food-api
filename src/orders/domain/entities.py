from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from shared.core.exceptions import ConflictException, ValidationException


class OrderStatus(StrEnum):
    PLACED = "PLACED"
    CANCELLED = "CANCELLED"


@dataclass
class OrderItem:
    product_id: int
    product_name: str
    quantity: int
    unit_price: int

    def __post_init__(self):
        if type(self.quantity) is not int or not 1 <= self.quantity <= 1000:
            raise ValidationException("Quantity must be between 1 and 1000.")
        if type(self.unit_price) is not int or not 0 <= self.unit_price <= 2_147_483_647:
            raise ValidationException("Unit price must be a nonnegative integer within database limits.")

    @property
    def total_price(self) -> int:
        return self.quantity * self.unit_price


@dataclass
class Order:
    user_id: UUID
    items: list[OrderItem]
    id: UUID = field(default_factory=uuid4)
    order_number: str = field(default_factory=lambda: "ORD-" + uuid4().hex.upper())
    ordered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: OrderStatus = OrderStatus.PLACED

    def __post_init__(self):
        if not 1 <= len(self.items) <= 20:
            raise ValidationException("An order must contain 1 to 20 items.")
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValidationException("Duplicate product IDs are not allowed.")
        if self.total_price < 0:
            raise ValidationException("Order total cannot be negative.")

    @property
    def total_price(self) -> int:
        return sum(item.total_price for item in self.items)

    def cancel(self):
        if self.status != OrderStatus.PLACED:
            raise ConflictException("Order has already been cancelled.")
        self.status = OrderStatus.CANCELLED
