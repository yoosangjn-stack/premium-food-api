"""한 요청에서 함께 쓰는 비동기 DB 세션과 모든 테이블의 공통 기반."""
import os
from datetime import datetime, timezone
from importlib import import_module
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.core.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


class Base(DeclarativeBase):
    """각 infrastructure/models.py가 상속하는 테이블의 공통 기반."""
    pass


class DateTimeBase:
    # 함수를 전달해야 행마다 생성 시각이 새로 계산됩니다.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    modified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, onupdate=lambda: datetime.now(timezone.utc), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, nullable=True
    )


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL or not DATABASE_URL.startswith("postgresql+asyncpg://"):
    raise RuntimeError("Set DATABASE_URL to a dedicated PostgreSQL database. See .env.example.")

POOL_SIZE = int(os.getenv("CONNECTION_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("CONNECTION_POOL_MAX_SIZE", "20"))
engine = create_async_engine(
    DATABASE_URL,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=30.0,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=os.getenv("SQL_ECHO", "False").lower() == "true",
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, autoflush=False, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """요청에 세션을 빌려주고, 실패하면 전체 작업을 되돌립니다."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    logger.info("데이터베이스 엔진 연결 풀을 종료합니다.")
    await engine.dispose()


def init_models():
    """create_all 전에 각 테이블을 Base.metadata에 등록합니다."""
    for feature in ("user", "auth", "board", "products", "orders"):
        import_module(f"{feature}.infrastructure.models")
