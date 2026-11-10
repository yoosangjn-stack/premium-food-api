import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv

from auth.domain.entities import TokenPayload
from auth.domain.service import TokenProvider
from shared.core.exceptions import UnauthorizedException


class JwtTokenProvider(TokenProvider):
    def __init__(
        self,
        secret_key: str | None = None,
        algorithm: str = "HS512",
        access_token_expire_minutes: int = 60,
    ):
        load_dotenv()
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", "")
        if len(self.secret_key.encode("utf-8")) < 64:
            raise RuntimeError("Set JWT_SECRET_KEY to a private random value of at least 64 bytes.")
        self.algorithm = algorithm
        self.expire_minutes = access_token_expire_minutes

    def create_access_token(self, user_id: uuid.UUID) -> tuple[str, str, datetime, int]:
        now = datetime.now(timezone.utc)
        expired_at = now + timedelta(minutes=self.expire_minutes)
        expires_in = self.expire_minutes * 60
        jti = str(uuid.uuid4())
        payload = {"sub": str(user_id), "jti": jti, "exp": expired_at, "iat": now}
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, jti, expired_at, expires_in

    def decode_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm],
                options={"require": ["sub", "jti", "exp", "iat"]},
            )
            if not isinstance(payload["sub"], str) or not isinstance(payload["jti"], str):
                raise ValueError("Invalid token identifiers")
            uuid.UUID(payload["jti"])
            return TokenPayload(
                user_id=uuid.UUID(payload["sub"]),
                jti=payload["jti"],
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            )
        except (jwt.PyJWTError, KeyError, ValueError, TypeError, OverflowError):
            raise UnauthorizedException("유효하지 않거나 만료된 토큰입니다.") from None
