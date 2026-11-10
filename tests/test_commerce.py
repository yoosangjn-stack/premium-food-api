"""Commerce API tests use only the isolated database fixture in conftest."""
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from orders.infrastructure.models import OrderModel


async def product(api, **changes):
    response = await api.client.post("/v1/products", headers=api.headers["admin"], json={
        "name": "Premium rice", "price": 12000, "stock_quantity": 10, **changes,
    })
    assert response.status_code == 201, response.text
    return response.json()


async def order(api, items, actor="owner"):
    return await api.client.post("/v1/orders", headers=api.headers[actor], json={"items": items})


async def stock(api, product_id):
    response = await api.client.get(f"/v1/products/{product_id}")
    assert response.status_code == 200
    return response.json()["stock_quantity"]


async def test_product_admin_permission_and_update(api):
    body = {"name": "Rice", "price": 1, "stock_quantity": 2}
    assert (await api.client.post("/v1/products", json=body)).status_code == 401
    assert (await api.client.post("/v1/products", json=body, headers=api.headers["owner"])).status_code == 403
    item = await product(api)
    path = f"/v1/products/{item['id']}"
    assert (await api.client.patch(path, json={"price": 3}, headers=api.headers["other"])).status_code == 403
    changed = await api.client.patch(path, json={"price": 0, "name": " Rice "}, headers=api.headers["admin"])
    assert changed.status_code == 200
    assert changed.json()["price"] == 0 and changed.json()["name"] == "Rice"
    assert (await api.client.get("/v1/products/2147483647")).status_code == 404


@pytest.mark.parametrize("changes", [{"price": -1}, {"price": 1.5}, {"price": True},
                                     {"stock_quantity": -1}, {"name": "   "}, {"price": 2147483648}])
async def test_invalid_product_data(api, changes):
    response = await api.client.post("/v1/products", headers=api.headers["admin"], json={
        "name": "Rice", "price": 1000, "stock_quantity": 1, **changes,
    })
    assert response.status_code == 422


async def test_product_search_filters_sort_and_page(api):
    a = await product(api, name="100%_rice", price=100, stock_quantity=1)
    b = await product(api, name="100xxrice", price=100, stock_quantity=2)
    await product(api, name="Sold rice", price=200, stock_quantity=0)
    literal = (await api.client.get("/v1/products", params={"q": "%_"})).json()
    assert literal["total"] == 1 and literal["items"][0]["id"] == a["id"]
    casefold = (await api.client.get("/v1/products", params={"q": "RICE"})).json()
    assert casefold["total"] == 3
    assert (await api.client.get("/v1/products", params={"page": 1000001})).status_code == 422
    assert (await api.client.get("/v1/products/2147483648")).status_code == 422
    page = (await api.client.get("/v1/products", params={
        "stock": "in_stock", "min_price": 100, "max_price": 100,
        "sort": "price", "page": 2, "size": 1,
    })).json()
    assert page["total"] == 2 and page["page"] == 2 and page["size"] == 1
    assert page["items"][0]["id"] == b["id"]
    sold = (await api.client.get("/v1/products", params={"stock": "sold_out"})).json()
    assert sold["total"] == 1
    assert (await api.client.get("/v1/products", params={"min_price": 200, "max_price": 100})).status_code == 422
    assert (await api.client.get("/v1/products", params={"sort": "price desc"})).status_code == 422


async def test_order_snapshots_and_owner_access(api):
    item = await product(api)
    created = await order(api, [{"product_id": item["id"], "quantity": 3}])
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["total_price"] == 36000 and body["status"] == "PLACED"
    assert body["items"][0]["total_price"] == 36000
    assert await stock(api, item["id"]) == 7
    path = f"/v1/orders/{body['id']}"
    await api.client.patch(f"/v1/products/{item['id']}", headers=api.headers["admin"], json={"name": "New", "price": 99})
    detail = await api.client.get(path, headers=api.headers["owner"])
    assert detail.json()["items"][0]["product_name"] == "Premium rice"
    assert detail.json()["items"][0]["unit_price"] == 12000
    assert (await api.client.get(path, headers=api.headers["other"])).status_code == 403
    assert (await api.client.get(path, headers=api.headers["admin"])).status_code == 200
    assert (await api.client.get("/v1/orders", headers=api.headers["other"])).json() == []
    assert len((await api.client.get("/v1/orders", headers=api.headers["owner"])).json()) == 1
    assert (await api.client.get(f"/v1/orders/{uuid4()}", headers=api.headers["owner"])).status_code == 404


async def test_failed_multiline_order_changes_nothing(api):
    a = await product(api, stock_quantity=4)
    b = await product(api, stock_quantity=0)
    response = await order(api, [{"product_id": a["id"], "quantity": 2}, {"product_id": b["id"], "quantity": 1}])
    assert response.status_code == 409
    assert await stock(api, a["id"]) == 4
    assert await stock(api, b["id"]) == 0
    async with api.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(OrderModel)) == 0


async def test_duplicate_invalid_or_unknown_order_items(api):
    item = await product(api)
    for items in ([], [{"product_id": item["id"], "quantity": 0}],
                  [{"product_id": item["id"], "quantity": 1001}],
                  [{"product_id": item["id"], "quantity": True}],
                  [{"product_id": item["id"], "quantity": 1}] * 2):
        assert (await order(api, items)).status_code == 422
    assert (await order(api, [{"product_id": 2147483647, "quantity": 1}])).status_code == 404
    assert await stock(api, item["id"]) == 10


@pytest.mark.parametrize("actor", ["owner", "admin"])
async def test_cancel_restores_once_and_rejects_others(api, actor):
    item = await product(api)
    created = (await order(api, [{"product_id": item["id"], "quantity": 2}])).json()
    path = f"/v1/orders/{created['id']}/cancel"
    assert (await api.client.post(path, headers=api.headers["other"])).status_code == 403
    assert await stock(api, item["id"]) == 8
    response = await api.client.post(path, headers=api.headers[actor])
    assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
    assert await stock(api, item["id"]) == 10
    assert (await api.client.post(path, headers=api.headers[actor])).status_code == 409
    assert await stock(api, item["id"]) == 10


async def test_order_insert_failure_rolls_back_stock(api, monkeypatch):
    from orders.infrastructure.repositories import SQLAlchemyOrderRepository
    item = await product(api)

    async def fail_insert(self, value):
        raise RuntimeError("Simulated insert failure after stock flush")

    monkeypatch.setattr(SQLAlchemyOrderRepository, "add", fail_insert)
    try:
        response = await order(api, [{"product_id": item["id"], "quantity": 2}])
        assert response.status_code == 500
    except RuntimeError as error:
        assert "Simulated insert failure" in str(error)
    assert await stock(api, item["id"]) == 10


async def test_cancellation_status_failure_rolls_back_stock(api, monkeypatch):
    from orders.infrastructure.repositories import SQLAlchemyOrderRepository
    item = await product(api)
    created = (await order(api, [{"product_id": item["id"], "quantity": 2}])).json()

    async def fail_status(self, value):
        raise RuntimeError("Simulated status failure after stock flush")

    monkeypatch.setattr(SQLAlchemyOrderRepository, "save_status", fail_status)
    try:
        response = await api.client.post(f"/v1/orders/{created['id']}/cancel", headers=api.headers["owner"])
        assert response.status_code == 500
    except RuntimeError as error:
        assert "Simulated status failure" in str(error)
    assert await stock(api, item["id"]) == 8
    detail = await api.client.get(f"/v1/orders/{created['id']}", headers=api.headers["owner"])
    assert detail.json()["status"] == "PLACED"
