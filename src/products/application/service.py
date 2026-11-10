from shared.domain.transaction import TransactionManager

from products.domain.entities import Product
from products.domain.repositories import ProductRepository
from shared.core.exceptions import NotFoundException, ValidationException


class ProductService:
    def __init__(self, repository: ProductRepository, transaction: TransactionManager):
        self.repository = repository
        self.transaction = transaction

    async def list_products(self, page: int = 1, size: int = 20, *, q: str | None = None,
                            stock: str | None = None, min_price: int | None = None,
                            max_price: int | None = None, sort: str = "id") -> dict:
        if not 1 <= page <= 1_000_000 or not 1 <= size <= 100:
            raise ValidationException("Invalid pagination.")
        if sort not in {"id", "price", "name"} or stock not in {None, "in_stock", "sold_out"}:
            raise ValidationException("Invalid product filter or sort.")
        if any(value is not None and value < 0 for value in (min_price, max_price)):
            raise ValidationException("Price filters must be nonnegative.")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValidationException("min_price cannot exceed max_price.")
        filters = dict(q=q, stock=stock, min_price=min_price, max_price=max_price)
        total = await self.repository.count(**filters)
        items = await self.repository.list((page - 1) * size, size, sort=sort, **filters)
        return {"items": items, "total": total, "page": page, "size": size}

    async def get_product(self, product_id: int) -> Product:
        product = await self.repository.find_by_id(product_id)
        if product is None:
            raise NotFoundException("Product not found.")
        return product

    async def create_product(self, name: str, price: int, stock_quantity: int) -> Product:
        try:
            result = await self.repository.save(Product(None, name, price, stock_quantity))
            await self.transaction.commit()
            return result
        except Exception:
            await self.transaction.rollback()
            raise

    async def update_product(self, product_id: int, changes: dict) -> Product:
        try:
            product = await self.repository.find_by_id(product_id, for_update=True)
            if product is None:
                raise NotFoundException("Product not found.")
            updated = Product(product.id, changes.get("name", product.name),
                              changes.get("price", product.price),
                              changes.get("stock_quantity", product.stock_quantity))
            result = await self.repository.save(updated)
            await self.transaction.commit()
            return result
        except Exception:
            await self.transaction.rollback()
            raise
