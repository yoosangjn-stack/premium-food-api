from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from shared.core.exceptions import SharedException
from shared.core.logger import get_logger
from shared.core.schemas import APIResponse

logger = get_logger(__name__)

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        codes = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        response = APIResponse.fail(code=codes.get(exc.status_code, "HTTP_ERROR"), message=str(exc.detail))
        return JSONResponse(status_code=exc.status_code, content=response.model_dump(mode="json"), headers=exc.headers)

    @app.exception_handler(IntegrityError)
    async def integrity_exception_handler(request: Request, exc: IntegrityError):
        # SQL과 입력값을 응답이나 로그에 노출하지 않습니다.
        response = APIResponse.fail(code="CONFLICT", message="중복되었거나 저장 조건에 맞지 않는 데이터입니다.")
        return JSONResponse(status_code=409, content=response.model_dump(mode="json"))

    # 비즈니스 예외 (SharedException 및 도메인 하위 예외)
    @app.exception_handler(SharedException)
    async def shared_exception_handler(request: Request, exc: SharedException):
        if exc.status_code >= 500:
            logger.error("비즈니스 서버 오류 [%s]: %s", exc.error_code, exc.message)
        else:
            logger.warning(
                "클라이언트 요청 예외 [%s]: %s (path: %s, method: %s)",
                exc.error_code,
                exc.message,
                request.url.path,
                request.method
            )

        response_dto = APIResponse.fail(
            code=exc.error_code,
            message=exc.message,
            errors=exc.errors
        )

        return JSONResponse(
            status_code=exc.status_code,
            content=response_dto.model_dump(mode='json'),
            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
        )

    # Pydantic 스키마 검증 실패 (422)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors_map: dict[str, list[str]] = {}
        for err in exc.errors():
            loc = ".".join(str(item) for item in err["loc"] if item != "body")
            field_name = loc if loc else "non_field_errors"
            errors_map.setdefault(field_name, []).append(err["msg"])

        logger.warning("요청 파라미터 유효성 검증 실패 (path: %s, method: %s): %s", request.url.path, request.method, errors_map)

        response_dto = APIResponse.fail(
            code="REQUEST_VALIDATION_ERROR",
            message="요청 입력값 검증에 실패했습니다.",
            errors=errors_map,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=response_dto.model_dump(mode="json"),
        )

    # 처리되지 않은 시스템 내부 오류 (500)
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error("처리되지 않은 서버 오류 (path: %s, method: %s, type: %s)", request.url.path, request.method, type(exc).__name__)

        response_dto = APIResponse.fail(
            code="INTERNAL_SERVER_ERROR",
            message="서버 내부 오류가 발생했습니다. 관리자에게 문의해주세요.",
            errors=None,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response_dto.model_dump(mode="json"),
        )
