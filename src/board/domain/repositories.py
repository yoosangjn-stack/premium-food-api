from abc import ABC, abstractmethod
from board.domain.board import Board
from board.domain.post import Comment
from board.domain.post import Post
from board.domain.enums import PostSearchType

class BoardRepository(ABC):
    @abstractmethod
    async def find_by_id(self, board_id: str) -> Board | None:
        """게시판 ID 기준으로 단건 조회 (삭제된 게시판 제외)"""
        pass

    @abstractmethod
    async def find_all(self, include_deleted: bool = False) -> list[Board]:
        """모든 게시판 설정 목록 조회"""
        pass

    @abstractmethod
    async def exists_by_id(self, board_id: str) -> bool:
        """해당 게시판 ID가 이미 존재하는지 여부 확인"""
        pass

    @abstractmethod
    async def save(self, board: Board) -> Board:
        """게시판 설정 등록 또는 수정"""
        pass


class CommentRepository(ABC):

    @abstractmethod
    async def find_by_id(self, comment_id: int) -> Comment | None:
        """댓글 ID 기준으로 단건 조회 (삭제된 댓글 제외)"""
        pass

    @abstractmethod
    async def find_by_post_id(self, post_id: int) -> list[Comment]:
        """특정 게시글에 작성된 댓글 전체 목록을 등록순(오름차순)으로 조회"""
        pass

    @abstractmethod
    async def count_by_post_id(self, post_id: int) -> int:
        """특정 게시글에 달린 유효 댓글 총 개수 카운트"""
        pass

    @abstractmethod
    async def save(self, comment: Comment) -> Comment:
        """댓글 등록 및 수정"""
        pass


class PostRepository(ABC):

    @abstractmethod
    async def find_by_id(self, post_id: int) -> Post | None:
        """게시글 ID 기준으로 단건 조회 (삭제된 글 제외)"""
        pass

    @abstractmethod
    async def find_by_board_id(
        self,
        board_id: str,
        limit: int,
        offset: int,
        search_type: PostSearchType | str | None = None,
        keyword: str | None = None,
    ) -> list[Post]:
        """특정 게시판의 게시글 목록을 최신순으로 페이징 조회"""
        pass

    @abstractmethod
    async def count_by_board_id(
        self,
        board_id: str,
        search_type: PostSearchType | str | None = None,
        keyword: str | None = None,
    ) -> int:
        """특정 게시판의 전체 유효 게시글 수 카운트 (페이지네이션 계산용)"""
        pass

    @abstractmethod
    async def save(self, post: Post) -> Post:
        """게시글 등록 또는 수정"""
        pass
