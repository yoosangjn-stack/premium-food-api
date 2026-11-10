"""Read-only HTML catalog integration tests; the api fixture rolls back all data."""
import html
import html.parser
import re
from urllib.parse import parse_qs, urlsplit

import pytest

from products.infrastructure.models import ProductModel


async def seed_product(api, name="한정 사과", price=12000, stock_quantity=3):
    async with api.sessions() as session:
        product = ProductModel(name=name, price=price, stock_quantity=stock_quantity)
        session.add(product)
        await session.commit()
        return product.id


async def test_catalog_uses_database_and_static_styles(api):
    product_id = await seed_product(api)
    response = await api.client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "한정 사과" in response.text
    assert "12,000" in response.text
    assert "3개" in response.text
    assert f"/products/{product_id}" in response.text
    assert "/docs" in response.text
    assert "/static/styles.css" in response.text
    style = await api.client.get("/static/styles.css")
    assert style.status_code == 200
    assert "text/css" in style.headers["content-type"]


async def test_catalog_filters_and_preserves_pagination(api):
    await seed_product(api, "한정 & 사과 A", price=9000)
    await seed_product(api, "한정 & 사과 B", price=15000)
    await seed_product(api, "한정 & 사과 C", price=18000, stock_quantity=0)
    params = {"q": "한정 & 사과", "stock": "in_stock", "min_price": "8000",
              "max_price": "17000", "sort": "price", "size": "1"}
    response = await api.client.get("/", params=params)
    assert response.status_code == 200
    assert "한정 &amp; 사과 A" in response.text
    assert "한정 &amp; 사과 B" not in response.text
    match = re.search(r'rel="next" href="([^"]+)"', response.text)
    assert match
    next_url = html.unescape(match.group(1))
    assert parse_qs(urlsplit(next_url).query) == {**{key: [value] for key, value in params.items()}, "page": ["2"]}
    next_response = await api.client.get(next_url)
    assert "한정 &amp; 사과 B" in next_response.text
    assert "한정 &amp; 사과 C" not in next_response.text
    assert 'rel="prev"' in next_response.text


async def test_catalog_and_detail_escape_product_names(api):
    unsafe = '<script>alert("test")</script>'
    product_id = await seed_product(api, unsafe, stock_quantity=0)
    for path in ("/", f"/products/{product_id}"):
        response = await api.client.get(path)
        assert response.status_code == 200
        assert unsafe not in response.text
        assert "&lt;script&gt;" in response.text
        assert "품절" in response.text
    response = await api.client.get("/", params={"q": unsafe})
    assert unsafe not in response.text
    assert "&lt;script&gt;" in response.text


async def test_catalog_empty_and_blank_price_fields(api):
    response = await api.client.get("/", params={"q": "no-matching-product", "min_price": "", "max_price": "", "stock": ""})
    assert response.status_code == 200
    assert "표시할 상품이 없습니다" in response.text


@pytest.mark.parametrize("params", [{"page": 0}, {"size": 101}, {"sort": "unsafe"},
    {"min_price": "-1"}, {"min_price": "9999999999"}, {"min_price": "10", "max_price": "1"}])
async def test_catalog_rejects_invalid_filters(api, params):
    response = await api.client.get("/", params=params)
    assert response.status_code == 422


async def test_unknown_product_has_html_404(api):
    response = await api.client.get("/products/2147483647")
    assert response.status_code == 404
    assert "text/html" in response.headers["content-type"]
    assert "상품을 찾을 수 없습니다" in response.text


async def test_catalog_does_not_accept_writes(api):
    response = await api.client.post("/", data={"name": "not a product"})
    assert response.status_code == 405

@pytest.mark.parametrize("path", ["/?page=1000001", "/products/2147483648"])
async def test_catalog_bounds_large_identifiers_and_pages(api, path):
    response = await api.client.get(path)
    assert response.status_code == 422

class StockOptionsParser(html.parser.HTMLParser):
    """Record actual option start tags inside the stock select, not text matches."""

    def __init__(self):
        super().__init__()
        self.in_stock_select = False
        self.options = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "select":
            self.in_stock_select = attributes.get("id") == "stock"
        elif tag == "option" and self.in_stock_select:
            self.options.append(attributes)

    def handle_endtag(self, tag):
        if tag == "select":
            self.in_stock_select = False


@pytest.mark.parametrize("stock", ["", "in_stock", "sold_out"])
async def test_catalog_renders_three_real_stock_options(api, stock):
    response = await api.client.get("/", params={"stock": stock})
    assert response.status_code == 200
    parser = StockOptionsParser()
    parser.feed(response.text)
    assert [option.get("value") for option in parser.options] == ["", "in_stock", "sold_out"]
    if stock:
        assert [option["value"] for option in parser.options if "selected" in option] == [stock]


async def test_blank_filters_never_render_none(api):
    response = await api.client.get("/", params={"q": "", "min_price": "", "max_price": ""})
    assert response.status_code == 200
    assert 'value="None"' not in response.text
    zero = await api.client.get("/", params={"min_price": "0", "max_price": "0"})
    assert zero.status_code == 200
    assert 'value="0"' in zero.text

async def test_request_info_logging(api, caplog):
    import logging
    with caplog.at_level(logging.INFO, logger="shared.core.middlewares"):
        response = await api.client.get("/health")
    assert response.status_code == 200
    assert any("status=200" in record.message and "duration_ms=" in record.message for record in caplog.records)
