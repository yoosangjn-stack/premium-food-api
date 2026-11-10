"""실제 PostgreSQL 테스트. 각 테스트의 데이터는 외부 트랜잭션 롤백으로 격리합니다."""
import os
import secrets
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
if not TEST_DATABASE_URL:
    raise pytest.UsageError("Set TEST_DATABASE_URL to a dedicated local premium_food_test database. See README.")
url = make_url(TEST_DATABASE_URL)
if url.host not in {"localhost", "127.0.0.1"} or url.database != "premium_food_test":
    raise pytest.UsageError("Tests only accept a local database named premium_food_test; never use real data.")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET_KEY"] = secrets.token_urlsafe(64)
os.environ["SQL_ECHO"] = "False"
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["CREATE_TABLES"] = "false"
os.environ["DEMO_SEED"] = "false"

from httpx import ASGITransport, AsyncClient
from main import app
from database import get_db
from database import Base, init_models
from user.infrastructure.models import UserModel
from user.infrastructure.security import BcryptPasswordHasher
from board.infrastructure.models import BoardModel
from wiring.auth import token_provider


@pytest.fixture(scope="session")
def password_hash():
    return BcryptPasswordHasher().hash("Validpass1!")


@pytest_asyncio.fixture
async def api(password_hash):
    engine = create_async_engine(TEST_DATABASE_URL)
    init_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        sessions = async_sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with sessions.begin() as session:
            users = {}
            headers = {}
            for name in ("owner", "other", "admin"):
                user = UserModel(
                    email=f"{name}@example.com", username=name, phone="010-0000-0000", name=name, password_hash=password_hash,
                    role="ADMIN" if name == "admin" else "USER", resign=False,
                )
                session.add(user)
                await session.flush()
                users[name] = user
                token, *_ = token_provider.create_access_token(user.id)
                headers[name] = {"Authorization": f"Bearer {token}"}
            session.add_all([
                BoardModel(board_id="free", board_name="Free", page_size=2,
                           edit_role="USER", comment_edit_role="USER"),
                BoardModel(board_id="guest", board_name="Guest"),
            ])

        async def override_db():
            async with sessions() as session:
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = override_db
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                yield SimpleNamespace(client=client, headers=headers, users=users, sessions=sessions)
        finally:
            app.dependency_overrides.pop(get_db, None)
            await transaction.rollback()
    await engine.dispose()
