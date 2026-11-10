from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from orders.domain.entities import OrderStatus


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: int = Field(gt=0, le=2_147_483_647, strict=True)
    quantity: int = Field(ge=1, le=1000, strict=True)


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[OrderItemCreate] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def reject_duplicate_products(self):
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Duplicate product IDs are not allowed.")
        return self


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    product_name: str
    quantity: int
    unit_price: int
    total_price: int


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_number: str
    user_id: UUID
    ordered_at: datetime
    status: OrderStatus
    items: list[OrderItemResponse]
    total_price: int
