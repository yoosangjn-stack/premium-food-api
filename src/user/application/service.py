import uuid

from shared.core.exceptions import ConflictException, NotFoundException
from shared.domain.transaction import TransactionManager
from user.domain.repository import UserRepository
from user.domain.service import PasswordHasher
from user.domain.user import User


class UserService:
    def __init__(self, repository: UserRepository, hasher: PasswordHasher, transaction: TransactionManager):
        self.repository = repository
        self.hasher = hasher
        self.transaction = transaction

    async def register_user(self, email: str, name: str, password: str, username: str, phone: str) -> User:
        try:
            email = email.strip().lower()
            username = username.strip().lower()
            if await self.repository.find_by_username(username):
                raise ConflictException("이미 사용 중인 아이디입니다.", error_code="USERNAME_ALREADY_EXISTS")
            if await self.repository.find_by_email(email):
                raise ConflictException("이미 사용 중인 이메일입니다.", error_code="EMAIL_ALREADY_EXISTS")
            user = User.create(username=username, phone=phone, email=email, name=name,
                               raw_password=password, hasher=self.hasher)
            saved = await self.repository.save(user)
            await self.transaction.commit()
            return saved
        except Exception:
            await self.transaction.rollback()
            raise

    async def change_password(self, user_id: uuid.UUID, old_password: str, new_password: str) -> None:
        try:
            user = await self.repository.find_by_id(user_id)
            if not user:
                raise NotFoundException("사용자를 찾을 수 없습니다.", error_code="USER_NOT_FOUND")
            user.change_password(old_password=old_password, new_password=new_password, hasher=self.hasher)
            await self.repository.save(user)
            await self.transaction.commit()
        except Exception:
            await self.transaction.rollback()
            raise
