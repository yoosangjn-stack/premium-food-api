from uuid import UUID
from auth.domain.service import UserCredentialVerifier
from user.domain.repository import UserRepository
from user.domain.service import PasswordHasher

# 실사용 비밀번호가 아닌 비교 전용 해시. 없는 이메일도 bcrypt 연산을 수행합니다.
DUMMY_PASSWORD_HASH = '$2b$12$WlLg9sjC1ZwbsI6kR8hw8u35cSgy1pxyMlm8noIlP6uYNIrKqN/Tu'


class UserCredentialVerifierImpl(UserCredentialVerifier):
    def __init__(self, user_repo: UserRepository, password_hasher: PasswordHasher):
        self._user_repo = user_repo
        self._password_hasher = password_hasher

    async def verify_credentials(self, email: str, plain_password: str) -> UUID | None:
        user = await self._user_repo.find_by_email(email)
        hashed = user.password_hash if user else DUMMY_PASSWORD_HASH
        valid = self._password_hasher.verify(plain_password, hashed)
        if not user or user.resign or not valid:
            return None
        return user.id
