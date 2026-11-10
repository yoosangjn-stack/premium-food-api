from dataclasses import dataclass

from shared.core.exceptions import ValidationException

MAX_INTEGER = 2_147_483_647


@dataclass
class Product:
    id: int | None
    name: str
    price: int
    stock_quantity: int

    def __post_init__(self):
        self.name = self.name.strip()
        if not self.name or len(self.name) > 100:
            raise ValidationException("Product name must contain 1 to 100 characters.")
        for value in (self.price, self.stock_quantity):
            if type(value) is not int or not 0 <= value <= MAX_INTEGER:
                raise ValidationException("Price and stock must be nonnegative integers within database limits.")

    def reduce_stock(self, quantity: int):
        if type(quantity) is not int or quantity < 1:
            raise ValidationException("Quantity must be a positive integer.")
        if self.stock_quantity < quantity:
            from shared.core.exceptions import ConflictException
            raise ConflictException(f"Insufficient stock for product {self.id}.")
        self.stock_quantity -= quantity

    def restore_stock(self, quantity: int):
        if type(quantity) is not int or quantity < 1:
            raise ValidationException("Quantity must be a positive integer.")
        if self.stock_quantity + quantity > MAX_INTEGER:
            from shared.core.exceptions import ConflictException
            raise ConflictException("Restoring stock would exceed the supported stock limit.")
        self.stock_quantity += quantity
