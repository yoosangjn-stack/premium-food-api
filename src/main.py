import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from wiring import wire_dependencies
from database import AsyncSessionLocal, close_db, engine
from database import Base, init_models
from shared.core.exception_handlers import register_exception_handlers
from shared.core.middlewares import register_middleware_handlers
from shared.infrastructure.demo_seed import seed_demo_data
from user.presentation.router import router as user_router
from auth.presentation.router import router as auth_router
from board.presentation.router import router as board_router
from products.presentation.router import router as product_router
from orders.presentation.router import router as order_router
from web.presentation.router import router as web_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_models()
    # create_all creates missing tables; it is not a migration tool.
    if os.getenv("CREATE_TABLES", "false").lower() == "true":
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    if os.getenv("DEMO_SEED", "false").lower() == "true":
        async with AsyncSessionLocal() as session:
            await seed_demo_data(session)
    try:
        yield
    finally:
        await close_db()

app = FastAPI(title="Premium Food API", version="1.0.0",
              description="한정수량 식품 주문·재고와 게시판: 교안 기반 4계층 학습 프로젝트", lifespan=lifespan)
register_exception_handlers(app)
register_middleware_handlers(app)
wire_dependencies(app)
for router in (user_router, auth_router, board_router):
    app.include_router(router)
for router in (product_router, order_router):
    app.include_router(router, prefix="/v1")
app.include_router(web_router)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}
