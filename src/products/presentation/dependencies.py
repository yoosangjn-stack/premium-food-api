from products.application.service import ProductService


def get_product_service() -> ProductService:
    raise NotImplementedError("ProductService dependency has not been wired.")
