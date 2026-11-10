from typing import Literal

from fastapi import APIRouter, Depends, Path, Query

from products.application.service import ProductService
from products.presentation.dependencies import get_product_service
from products.presentation.schemas import ProductCreate, ProductResponse, ProductUpdate, ProductPageResponse
from user.presentation.dependencies import require_admin

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=ProductPageResponse)
async def list_products(page: int = Query(1, ge=1, le=1_000_000), size: int = Query(20, ge=1, le=100),
                        q: str | None = Query(None, max_length=100),
                        stock: Literal["in_stock", "sold_out"] | None = None,
                        min_price: int | None = Query(None, ge=0, le=2_147_483_647),
                        max_price: int | None = Query(None, ge=0, le=2_147_483_647),
                        sort: Literal["id", "price", "name"] = "id",
                        service: ProductService = Depends(get_product_service)):
    return await service.list_products(page, size, q=q, stock=stock,
                                       min_price=min_price, max_price=max_price, sort=sort)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int = Path(gt=0, le=2_147_483_647), service: ProductService = Depends(get_product_service)):
    return await service.get_product(product_id)


@router.post("", response_model=ProductResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_product(data: ProductCreate, service: ProductService = Depends(get_product_service)):
    return await service.create_product(**data.model_dump())


@router.patch("/{product_id}", response_model=ProductResponse, dependencies=[Depends(require_admin)])
async def update_product(data: ProductUpdate, product_id: int = Path(gt=0, le=2_147_483_647),
                         service: ProductService = Depends(get_product_service)):
    return await service.update_product(product_id, data.model_dump(exclude_unset=True))
