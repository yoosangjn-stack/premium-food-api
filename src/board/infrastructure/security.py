import bcrypt
from board.domain.service import PasswordHasher
from shared.core.exceptions import ValidationException


class BcryptPasswordHasher(PasswordHasher):
    def hash(self, raw_password: str) -> str:
        password_bytes = raw_password.encode("utf-8")
        if len(password_bytes) > 72:
            raise ValidationException(
                message="비밀번호는 UTF-8 기준 72바이트 이하여야 합니다.",
                field_errors={"password": ["비밀번호가 너무 깁니다."]},
            )
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")

    def verify(self, raw_password: str, hashed_password: str) -> bool:
        password_bytes = raw_password.encode("utf-8")
        if len(password_bytes) > 72:
            return False
        try:
            return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
        except ValueError:
            return False
