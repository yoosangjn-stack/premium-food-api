from shared.infrastructure.transaction import SQLAlchemyTransactionManager
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from board.presentation.dependencies import (
    get_current_author,
    get_current_role,
    provide_board_repository,
    provide_board_service,
    provide_comment_repository,
    provide_comment_service,
    provide_post_repository,
    provide_post_service,
    require_admin_role,
)

from board.application.service import BoardService, CommentService, PostService
from board.domain.repositories import BoardRepository
from board.domain.repositories import CommentRepository
from board.domain.repositories import PostRepository
from board.domain.enums import Role
from board.domain.post import Author
from database import get_db
from shared.core.exceptions import ForbiddenException

from board.infrastructure.repositories import SqlAlchemyBoardRepository
from board.infrastructure.repositories import SqlAlchemyPostRepository
from board.infrastructure.repositories import SqlAlchemyCommentRepository
from board.infrastructure.security import BcryptPasswordHasher

from user.presentation.dependencies import get_optional_user

_password_hasher = BcryptPasswordHasher()

def create_board_repository(session: AsyncSession = Depends(get_db)) -> BoardRepository:
        return SqlAlchemyBoardRepository(session)

def create_post_repository(session: AsyncSession = Depends(get_db)) -> PostRepository:
    return SqlAlchemyPostRepository(session)

def create_comment_repository(session: AsyncSession = Depends(get_db)) -> CommentRepository:
    return SqlAlchemyCommentRepository(session)

def create_board_service(
    repo: BoardRepository = Depends(create_board_repository),
    session: AsyncSession = Depends(get_db),
) -> BoardService:
    return BoardService(board_repo=repo, transaction=SQLAlchemyTransactionManager(session))

def create_post_service(
    post_repo: PostRepository = Depends(create_post_repository),
    board_repo: BoardRepository = Depends(create_board_repository),
    session: AsyncSession = Depends(get_db),
) -> PostService:
    return PostService(
        post_repo=post_repo,
        board_repo=board_repo,
        password_hasher=_password_hasher,
        transaction=SQLAlchemyTransactionManager(session),
    )

def create_comment_service(
    comment_repo: CommentRepository = Depends(create_comment_repository),
    post_repo: PostRepository = Depends(create_post_repository),
    board_repo: BoardRepository = Depends(create_board_repository),
    session: AsyncSession = Depends(get_db),
) -> CommentService:
    return CommentService(
        comment_repo=comment_repo,
        post_repo=post_repo,
        board_repo=board_repo,
        password_hasher=_password_hasher,
        transaction=SQLAlchemyTransactionManager(session),
    )


# None - 미로그인 사용자
async def _get_current_role(user=Depends(get_optional_user)) -> Role | None:
    if not user:
        return None
    return Role(user.role)

async def _get_current_author(user=Depends(get_optional_user)) -> Author | None:
    if not user:
        return None

    return Author.member(user_id=user.id, username=user.username)


async def _require_admin_role(role: Role | None = Depends(_get_current_role)) -> Role:
    if role != Role.ADMIN:
        raise ForbiddenException("관리자 권한이 필요합니다.")

    return role

def wire_board_dependencies(app: FastAPI) -> None:

    app.dependency_overrides.update(
        {
            provide_board_repository: create_board_repository,
            provide_post_repository: create_post_repository,
            provide_comment_repository: create_comment_repository,

            provide_board_service: create_board_service,
            provide_post_service: create_post_service,
            provide_comment_service: create_comment_service,

            get_current_role: _get_current_role,
            get_current_author: _get_current_author,
            require_admin_role: _require_admin_role,
        }
    )
