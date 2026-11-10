import logging
import os
import time
import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from shared.core.schemas import APIResponse

logger = logging.getLogger(__name__)

def register_middleware_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_request(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Stack frames aid debugging; exception text can contain SQL parameter secrets.
            logger.error("Unhandled %s\n%s", type(exc).__name__, "".join(traceback.format_tb(exc.__traceback__)))
            body = APIResponse.fail(code="INTERNAL_SERVER_ERROR", message="서버 내부 오류가 발생했습니다.")
            response = JSONResponse(status_code=500, content=body.model_dump(mode="json"))
        elapsed = (time.perf_counter() - started) * 1000
        # Do not log bodies, raw paths/query strings, headers, or tokens.
        route = request.scope.get("route")
        logger.info("%s %s status=%d duration_ms=%.1f", request.method,
                    route.path if route else "/unmatched", response.status_code, elapsed)
        response.headers["X-Process-Time-Ms"] = f"{elapsed:.1f}"
        return response

    origins = [value.strip() for value in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if value.strip()]
    # Added last: wraps the logging/error boundary so 500 responses also receive CORS headers.
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])
