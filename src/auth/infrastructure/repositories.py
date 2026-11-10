from datetime import datetime
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from auth.domain.repository import TokenBlacklistRepository
from auth.infrastructure.models import TokenBlacklistModel

class SqlAlchemyTokenBlacklistRepository(TokenBlacklistRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, jti: str, expired_at: datetime) -> None:
        """블랙리스트에 토큰 식별자 등록"""
        stmt = insert(TokenBlacklistModel).values(jti=jti, expired_at=expired_at).on_conflict_do_nothing(index_elements=["jti"])
        await self.session.execute(stmt)
        await self.session.flush()

    async def is_blacklisted(self, jti: str) -> bool:
        """토큰이 블랙리스트에 등록되어 있는지 확인"""
        stmt = select(TokenBlacklistModel.jti).where(TokenBlacklistModel.jti == jti)
        result = await self.session.scalar(stmt)
        return result is not None

    async def cleanup_expired(self, current_time: datetime) -> int:
        """유효기간이 지난 블랙리스트 항목 정리"""
        stmt= delete(TokenBlacklistModel).where(TokenBlacklistModel.expired_at <= current_time)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
