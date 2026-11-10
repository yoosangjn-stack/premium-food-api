"""Real PostgreSQL connections prove stock safety under competing requests.

Unlike the api fixture, seed data is committed and visible to both connections.
Only rows belonging to this fixture's UUID user/product are deleted afterward.
"""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from conftest import TEST_DATABASE_URL
from auth.infrastructure.models import TokenBlacklistModel
from main import app
from orders.infrastructure.models import OrderItemModel, OrderModel
from products.infrastructure.models import ProductModel
from database import get_db
from database import Base, init_models
from user.infrastructure.models import UserModel
from wiring.auth import token_provider


class RequestStartBarrier:
    """Hold two requests until each owns a different database connection."""

    def __init__(self):
        self.enabled = False
        self.backend_ids = []
        self.ready = asyncio.Event()

    def arm(self):
        self.backend_ids.clear()
        self.ready.clear()
        self.enabled = True

    async def wait(self, session):
        if not self.enabled:
            return
        backend_id = await session.scalar(text("SELECT pg_backend_pid()"))
        self.backend_ids.append(backend_id)
        if len(self.backend_ids) == 2:
            self.enabled = False
            self.ready.set()
        await asyncio.wait_for(self.ready.wait(), timeout=10)


@pytest_asyncio.fixture
async def concurrent_api(password_hash):
    # conftest validates the local dedicated test database before collection.
    engine = create_async_engine(
        TEST_DATABASE_URL, pool_size=4, max_overflow=0, pool_timeout=10,
        connect_args={"server_settings": {"lock_timeout": "10000", "statement_timeout": "15000"}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid4()
    suffix = user_id.hex[:20]
    product_id = None
    token_jti = None
    barrier = RequestStartBarrier()
    previous_override = app.dependency_overrides.get(get_db)
    override_installed = False

    try:
        init_models()
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        # Committed fixtures are required: other connections cannot see an outer rollback fixture.
        async with sessions.begin() as session:
            session.add(UserModel(
                id=user_id, username=f"race_{suffix}", email=f"race_{suffix}@example.com",
                name="Concurrency test", phone="010-0000-0000", password_hash=password_hash,
                role="USER", resign=False,
            ))
            product = ProductModel(name=f"race_{suffix}", price=1000, stock_quantity=1)
            session.add(product)
            await session.flush()
            product_id = product.id

        async def override_db():
            # One session/connection per HTTP request, never a shared outer transaction.
            async with sessions() as session:
                try:
                    await barrier.wait(session)
                    yield session
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_db
        override_installed = True
        token, *_ = token_provider.create_access_token(user_id)
        token_jti = token_provider.decode_token(token).jti
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield SimpleNamespace(
                client=client, headers={"Authorization": f"Bearer {token}"},
                user_id=user_id, product_id=product_id, sessions=sessions, barrier=barrier,
            )
    finally:
        if override_installed:
            if previous_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_override
        try:
            # Exact fixture ownership filters; no table-wide delete/drop/truncate.
            async with sessions.begin() as session:
                if token_jti:
                    await session.execute(delete(TokenBlacklistModel).where(TokenBlacklistModel.jti == token_jti))
                own_order_ids = select(OrderModel.id).where(OrderModel.user_id == user_id)
                await session.execute(delete(OrderItemModel).where(OrderItemModel.order_id.in_(own_order_ids)))
                await session.execute(delete(OrderModel).where(OrderModel.user_id == user_id))
                if product_id is not None:
                    await session.execute(delete(ProductModel).where(ProductModel.id == product_id))
                await session.execute(delete(UserModel).where(UserModel.id == user_id))
        finally:
            await engine.dispose()


async def run_two_requests(api, path, body=None):
    api.barrier.arm()

    async def send():
        return await api.client.post(path, headers=api.headers, json=body)

    # Await both even if one raises, so cleanup never races a still-running request.
    results = await asyncio.gather(send(), send(), return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    assert len(set(api.barrier.backend_ids)) == 2, "Requests must use separate PostgreSQL connections"
    return results


async def test_competing_orders_cannot_oversell(concurrent_api):
    api = concurrent_api
    responses = await run_two_requests(api, "/v1/orders", {
        "items": [{"product_id": api.product_id, "quantity": 1}],
    })
    assert sorted(response.status_code for response in responses) == [201, 409], [r.text for r in responses]
    async with api.sessions() as session:
        product = await session.get(ProductModel, api.product_id)
        assert product.stock_quantity == 0
        count = await session.scalar(select(func.count()).select_from(OrderModel).where(OrderModel.user_id == api.user_id))
        assert count == 1
        order = await session.scalar(select(OrderModel).where(OrderModel.user_id == api.user_id))
        assert order.status == "PLACED" and order.total_price == 1000
        quantity = await session.scalar(select(func.sum(OrderItemModel.quantity)).where(OrderItemModel.order_id == order.id))
        assert quantity == 1


async def test_competing_cancellations_restore_stock_once(concurrent_api):
    api = concurrent_api
    created = await api.client.post("/v1/orders", headers=api.headers, json={
        "items": [{"product_id": api.product_id, "quantity": 1}],
    })
    assert created.status_code == 201, created.text
    order_id = created.json()["id"]
    responses = await run_two_requests(api, f"/v1/orders/{order_id}/cancel")
    assert sorted(response.status_code for response in responses) == [200, 409], [r.text for r in responses]
    async with api.sessions() as session:
        product = await session.get(ProductModel, api.product_id)
        assert product.stock_quantity == 1
        order = await session.scalar(select(OrderModel).where(OrderModel.user_id == api.user_id))
        assert order.status == "CANCELLED"
        count = await session.scalar(select(func.count()).select_from(OrderModel).where(OrderModel.user_id == api.user_id))
        assert count == 1

async def test_competing_logouts_are_idempotent(concurrent_api):
    api = concurrent_api
    responses = await run_two_requests(api, "/v1/auth/logout")
    assert [response.status_code for response in responses] == [204, 204], [r.text for r in responses]
    blocked = await api.client.get("/v1/orders", headers=api.headers)
    assert blocked.status_code == 401
