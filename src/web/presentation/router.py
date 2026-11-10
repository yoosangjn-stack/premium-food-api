from pathlib import Path
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Path as PathParameter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from products.application.service import ProductService
from products.presentation.dependencies import get_product_service
from shared.core.exceptions import NotFoundException

WEB_DIRECTORY = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(WEB_DIRECTORY / "templates"))
router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def catalog(
    request: Request,
    page: int = Query(1, ge=1, le=1_000_000),
    size: int = Query(12, ge=1, le=100),
    q: str | None = Query(None, max_length=100),
    stock: Literal["", "in_stock", "sold_out"] = "",
    min_price: str = Query("", max_length=10, pattern=r"^\d*$"),
    max_price: str = Query("", max_length=10, pattern=r"^\d*$"),
    sort: Literal["id", "price", "name"] = "id",
    service: ProductService = Depends(get_product_service),
):
    # Empty HTML number inputs are empty strings, not null values.
    minimum = int(min_price) if min_price else None
    maximum = int(max_price) if max_price else None
    error = None
    if any(value is not None and value > 2_147_483_647 for value in (minimum, maximum)):
        error = "가격은 2,147,483,647원 이하로 입력해 주세요."
    elif minimum is not None and maximum is not None and minimum > maximum:
        error = "최소 가격은 최대 가격보다 클 수 없습니다."
    filters = dict(q=q or "", stock=stock, min_price=min_price, max_price=max_price, sort=sort, size=size)
    result = {"items": [], "total": 0, "page": page, "size": size}
    if error is None:
        result = await service.list_products(page, size, q=q or None, stock=stock or None,
                                             min_price=minimum, max_price=maximum, sort=sort)
    pages = max(1, (result["total"] + size - 1) // size)

    def page_url(target: int) -> str:
        return f"{request.url_for('catalog').path}?{urlencode({**filters, 'page': target})}"

    return templates.TemplateResponse(
        request=request, name="catalog.html",
        context={**result, "filters": filters, "pages": pages, "error": error,
                 "previous_url": page_url(page - 1) if page > 1 else None,
                 "next_url": page_url(page + 1) if page < pages else None},
        status_code=422 if error else 200,
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: int = PathParameter(gt=0, le=2_147_483_647),
                         service: ProductService = Depends(get_product_service)):
    try:
        product = await service.get_product(product_id)
    except NotFoundException:
        return templates.TemplateResponse(request=request, name="not_found.html", status_code=404)
    return templates.TemplateResponse(request=request, name="product.html", context={"product": product})
