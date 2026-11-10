from typing import Generic, TypeVar

T = TypeVar("T")


class SharedException(Exception, Generic[T]):
    """모든 애플리케이션 예외의 공통 부모 클래스"""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "BAD_REQUEST",
        errors: T | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.errors: T | None = errors
        super().__init__(message)


class BadRequestException(SharedException[T]):
    def __init__(
        self,
        message: str,
        error_code: str = "BAD_REQUEST",
        errors: T | None = None,
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_code=error_code,
            errors=errors,
        )


class UnauthorizedException(SharedException[None]):
    def __init__(
        self,
        message: str = "인증되지 않은 사용자입니다.",
        error_code: str = "UNAUTHORIZED",
    ):
        super().__init__(
            message=message,
            status_code=401,
            error_code=error_code,
            errors=None,
        )


class ForbiddenException(SharedException[None]):
    def __init__(
        self,
        message: str = "리소스에 접근할 권한이 없습니다.",
        error_code: str = "FORBIDDEN",
    ):
        super().__init__(
            message=message,
            status_code=403,
            error_code=error_code,
            errors=None,
        )


class NotFoundException(SharedException[None]):
    def __init__(
        self,
        message: str = "리소스를 찾을 수 없습니다.",
        error_code: str = "NOT_FOUND",
    ):
        super().__init__(
            message=message,
            status_code=404,
            error_code=error_code,
            errors=None,
        )


class ConflictException(SharedException[None]):
    def __init__(
        self,
        message: str = "리소스가 이미 존재합니다.",
        error_code: str = "CONFLICT",
    ):
        super().__init__(
            message=message,
            status_code=409,
            error_code=error_code,
            errors=None,
        )


class ValidationException(SharedException[dict[str, list[str]]]):
    def __init__(
        self,
        message: str = "유효성 검사에 실패했습니다.",
        error_code: str = "VALIDATION_ERROR",
        field_errors: dict[str, list[str]] | None = None,
    ):
        super().__init__(
            message=message,
            status_code=422,
            error_code=error_code,
            errors=field_errors or {},
        )
