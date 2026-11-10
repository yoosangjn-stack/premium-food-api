"""Opt-in learning data only; never called unless DEMO_SEED=true."""
from sqlalchemy import select, func
from products.infrastructure.models import ProductModel
from board.infrastructure.models import BoardModel

DEMO_NAMES = ["프리미엄 사과", "제주 감귤", "신고 배", "샤인머스캣", "햇밤", "청송 사과", "대저 토마토", "완숙 토마토", "설향 딸기", "블루베리", "유기농 당근", "햇감자", "단호박", "찰옥수수", "표고버섯", "고구마", "완도 미역", "기장 다시마", "제주 한라봉", "진영 단감"]

async def seed_demo_data(session) -> None:
    # Existing products/stock must never be reset by a restart.
    if await session.scalar(select(func.count()).select_from(ProductModel)) == 0:
        session.add_all([ProductModel(name=name, price=5000 + index * 1000,
                                     stock_quantity=5 + index % 6)
                         for index, name in enumerate(DEMO_NAMES)])
    if await session.get(BoardModel, "free") is None:
        session.add(BoardModel(board_id="free", board_name="자유 게시판",
                               page_size=20, edit_role="USER", comment_edit_role="USER"))
    await session.commit()
