from typing import Annotated
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from shared.core.exceptions import UnauthorizedException

from auth.application.service import AuthService
from auth.presentation.dependencies import provide_auth_service, oauth2_scheme
from auth.presentation.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/v1/auth", tags=["Auth"])



@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="로그인",
    description="이메일과 비밀번호를 검증하여 JWT 액세스 토큰(HS512)을 발급합니다.",
)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(provide_auth_service)],
):
    """이메일/비밀번호 인증 후 JWT 토큰 발급"""
    token, token_type, expires_in = await auth_service.login(request.email, request.password)
    return TokenResponse(
        access_token=token,
        token_type=token_type,
        expires_in=expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="로그아웃",
    description="현재 전달된 JWT 액세스 토큰의 식별자(jti)를 블랙리스트 DB에 등록하여 세션을 무효화합니다.",
)
async def logout(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    auth_service: Annotated[AuthService, Depends(provide_auth_service)],
):
    """현재 사용 중인 토큰을 블랙리스트에 등록하여 즉시 만료 처리"""
    if not token:
        raise UnauthorizedException("Bearer 토큰이 필요합니다.")
    await auth_service.logout(token)
    return None

@router.post("/token", response_model=TokenResponse, summary="OAuth2 토큰 발급")
async def issue_token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: Annotated[AuthService, Depends(provide_auth_service)],
):
    """Swagger 로그인: username 칸에 이메일을 입력하세요."""
    token, token_type, expires_in = await auth_service.login(form.username, form.password)
    return TokenResponse(access_token=token, token_type=token_type, expires_in=expires_in)
