from orders.application.service import OrderService


def get_order_service() -> OrderService:
    raise NotImplementedError("OrderService dependency has not been wired.")
