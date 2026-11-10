import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from shared.core.exceptions import ConflictException
from sqlalchemy.ext.asyncio import AsyncSession
from user.domain.repository import UserRepository
from user.domain.user import User
from user.infrastructure.models import UserModel

class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        user_model = await self.session.scalar(stmt)
        return user_model.to_user() if user_model else None

    async def find_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        user_model = await self.session.scalar(stmt)
        return user_model.to_user() if user_model else None

    async def find_by_username(self, username: str) -> User | None:
        model = await self.session.scalar(select(UserModel).where(UserModel.username == username))
        return model.to_user() if model else None

    async def save(self, user: User) -> User:
        if user.id is None:
            # 신규 사용자 등록(INSERT)
            user_model = UserModel(
                username=user.username,
                phone=user.phone,
                email=user.email,
                name=user.name,
                password_hash=user.password_hash,
                role=user.role,
                resign=user.resign
            )
            self.session.add(user_model)
            await self._flush()
            await self.session.refresh(user_model)
            return user_model.to_user()

        # 기존 사용자 정보 수정(UPDATE)
        stmt = select(UserModel).where(UserModel.id == user.id)
        user_model = await self.session.scalar(stmt)

        if user_model:
            user_model.username = user.username
            user_model.phone = user.phone
            user_model.email = user.email
            user_model.name = user.name
            user_model.password_hash = user.password_hash
            user_model.resign = user.resign
            user_model.deleted_at = user.deleted_at
            user_model.modified_at = user.modified_at

            await self._flush()
            await self.session.refresh(user_model)
            return user_model.to_user()

        return user

    async def _flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            # Translate database uniqueness races without exposing SQL or credentials.
            detail = str(exc.orig).lower()
            if "username" in detail:
                raise ConflictException("이미 사용 중인 아이디입니다.", error_code="USERNAME_ALREADY_EXISTS") from None
            if "email" in detail:
                raise ConflictException("이미 사용 중인 이메일입니다.", error_code="EMAIL_ALREADY_EXISTS") from None
            raise
