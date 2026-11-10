from sqlalchemy import func, select
from shared.core.exceptions import ConflictException
from sqlalchemy.ext.asyncio import AsyncSession
from board.domain.board import Board
from board.domain.repositories import BoardRepository
from board.infrastructure.mappers import BoardMapper
from board.infrastructure.models import BoardModel
from board.domain.post import Comment
from board.domain.repositories import CommentRepository
from board.infrastructure.mappers import CommentMapper
from board.infrastructure.models import CommentModel
from sqlalchemy import func, or_, select
from board.domain.enums import PostSearchType
from board.domain.post import Post
from board.domain.repositories import PostRepository
from board.infrastructure.mappers import PostMapper
from board.infrastructure.models import PostModel

class SqlAlchemyBoardRepository(BoardRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_id(self, board_id: str) -> Board | None:
        """게시판 ID 기준으로 단건 조회 (삭제된 게시판 제외)"""
        stmt = select(BoardModel).where(
            BoardModel.board_id == board_id,
            BoardModel.deleted_at.is_(None),
        )
        model = await self.session.scalar(stmt)

        return BoardMapper.to_domain(model) if model else None

    async def find_all(self, include_deleted: bool = False) -> list[Board]:
        """모든 게시판 설정 목록 조회"""

        stmt = select(BoardModel)
        if not include_deleted: # 삭제 게시글 미포함
            stmt = stmt.where(BoardModel.deleted_at.is_(None))

        models = (await self.session.scalars(stmt)).all()

        return [BoardMapper.to_domain(model) for model in models]

    async def exists_by_id(self, board_id: str) -> bool:
        """해당 게시판 ID가 이미 존재하는지 여부 확인"""
        stmt = select(func.count(BoardModel.board_id)).where(
            BoardModel.board_id == board_id,
        )

        count = await self.session.scalar(stmt)
        return (count or 0) > 0

    async def save(self, board: Board) -> Board:
        """게시판 설정 등록 또는 수정"""
        _board = await self.session.get(BoardModel, board.board_id)
        if _board: # 게시글이 있다면 수정
            if board.created_at is None:
                raise ConflictException("이미 사용한 게시판 ID입니다.")
            _board.board_name = board.board_name
            _board.page_size = board.page_size
            _board.edit_role = board.authority.edit_role.value
            _board.view_role = board.authority.view_role.value
            _board.list_role = board.authority.list_role.value
            _board.comment_list_role = board.authority.comment_list_role.value
            _board.comment_edit_role = board.authority.comment_edit_role.value
            _board.deleted_at = board.deleted_at
            _board.modified_at = board.modified_at

            await self.session.flush()
            await self.session.refresh(_board)
            return BoardMapper.to_domain(_board)
        else: # 게시글 등록
            new_model = BoardMapper.to_model(board)
            self.session.add(new_model)

            await self.session.flush()
            await self.session.refresh(new_model)
            return BoardMapper.to_domain(new_model)


class SqlAlchemyCommentRepository(CommentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_id(self, comment_id: int) -> Comment | None:
        """댓글 ID 기준으로 단건 조회 (삭제된 댓글 제외)"""
        stmt = select(CommentModel).where(
            CommentModel.comment_id == comment_id,
            CommentModel.deleted_at.is_(None)
        )

        model = await self.session.scalar(stmt)
        return CommentMapper.to_domain(model) if model else None

    async def find_by_post_id(self, post_id: int) -> list[Comment]:
        """특정 게시글에 작성된 댓글 전체 목록을 등록순(오름차순)으로 조회"""
        stmt = (
            select(CommentModel)
            .where(
                CommentModel.post_id == post_id,
                CommentModel.deleted_at.is_(None),
            )
            .order_by(CommentModel.comment_id.asc())
        )
        models = (await self.session.scalars(stmt)).all()
        return [CommentMapper.to_domain(model) for model in models]

    async def count_by_post_id(self, post_id: int) -> int:
        """특정 게시글에 달린 유효 댓글 총 개수 카운트"""
        stmt = select(func.count(CommentModel.comment_id)).where(
            CommentModel.post_id == post_id,
            CommentModel.deleted_at.is_(None),
        )

        count = await self.session.scalar(stmt)
        return count or 0

    async def save(self, comment: Comment) -> Comment:
        """댓글 등록 및 수정"""
        if comment.comment_id:
            _comment = await self.session.get(CommentModel, comment.comment_id)
            if _comment: # 댓글 수정
                _comment.content = comment.content
                _comment.deleted_at = comment.deleted_at
                _comment.modified_at = comment.modified_at
                await self.session.flush()
                await self.session.refresh(_comment)
                return CommentMapper.to_domain(_comment)

        # 댓글 추가
        new_model = CommentMapper.to_model(comment)
        self.session.add(new_model)
        await self.session.flush()
        await self.session.refresh(new_model)
        return CommentMapper.to_domain(new_model)


class SqlAlchemyPostRepository(PostRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _build_search_filter(self, search_type, keyword):
        """공개 정보인 제목·본문·작성자 이름만 검색합니다. %와 _도 문자로 취급합니다."""
        if not keyword or not keyword.strip():
            return None
        keyword = keyword.strip()
        title = PostModel.title.icontains(keyword, autoescape=True)
        content = PostModel.content.icontains(keyword, autoescape=True)
        author = PostModel.author_name.icontains(keyword, autoescape=True)
        match search_type:
            case PostSearchType.TITLE:
                return title
            case PostSearchType.CONTENT:
                return content
            case PostSearchType.TITLE_CONTENT:
                return or_(title, content)
            case PostSearchType.AUTHOR_NAME:
                return author
            case _:
                return or_(title, content, author)

    def _conditions(self, board_id, search_type, keyword):
        conditions = [PostModel.board_id == board_id, PostModel.deleted_at.is_(None)]
        search = self._build_search_filter(search_type, keyword)
        if search is not None:
            conditions.append(search)
        return conditions

    async def find_by_id(self, post_id: int) -> Post | None:
        model = await self.session.scalar(select(PostModel).where(
            PostModel.post_id == post_id, PostModel.deleted_at.is_(None),
        ))
        return PostMapper.to_domain(model) if model else None

    async def find_by_board_id(
        self, board_id: str, limit: int, offset: int,
        search_type: PostSearchType | str | None = None, keyword: str | None = None,
    ) -> list[Post]:
        stmt = (select(PostModel)
                .where(*self._conditions(board_id, search_type, keyword))
                .order_by(PostModel.post_id.desc()).offset(offset).limit(limit))
        return [PostMapper.to_domain(model) for model in (await self.session.scalars(stmt)).all()]

    async def count_by_board_id(
        self, board_id: str, search_type: PostSearchType | str | None = None,
        keyword: str | None = None,
    ) -> int:
        stmt = select(func.count(PostModel.post_id)).where(*self._conditions(board_id, search_type, keyword))
        return (await self.session.scalar(stmt)) or 0

    async def save(self, post: Post) -> Post:
        if post.post_id:
            model = await self.session.get(PostModel, post.post_id)
            if model:
                model.title = post.title
                model.content = post.content
                model.deleted_at = post.deleted_at
                model.modified_at = post.modified_at
                await self.session.flush()
                await self.session.refresh(model)
                return PostMapper.to_domain(model)
        model = PostMapper.to_model(post)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return PostMapper.to_domain(model)
