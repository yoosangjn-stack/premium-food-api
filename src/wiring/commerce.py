"""Compose concrete commerce dependencies outside the presentation layer."""
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from orders.application.service import OrderService
from orders.infrastructure.repositories import SQLAlchemyOrderRepository
from orders.presentation.dependencies import get_order_service
from products.application.service import ProductService
from products.infrastructure.repositories import SQLAlchemyProductRepository
from products.presentation.dependencies import get_product_service
from database import get_db
from shared.infrastructure.transaction import SQLAlchemyTransactionManager


def create_product_service(session: AsyncSession = Depends(get_db)) -> ProductService:
    return ProductService(
        repository=SQLAlchemyProductRepository(session),
        transaction=SQLAlchemyTransactionManager(session),
    )


def create_order_service(session: AsyncSession = Depends(get_db)) -> OrderService:
    return OrderService(
        orders=SQLAlchemyOrderRepository(session),
        products=SQLAlchemyProductRepository(session),
        transaction=SQLAlchemyTransactionManager(session),
    )


def wire_commerce_dependencies(app: FastAPI) -> None:
    app.dependency_overrides.update({
        get_product_service: create_product_service,
        get_order_service: create_order_service,
    })
