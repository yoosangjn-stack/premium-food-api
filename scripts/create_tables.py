"""새 학습 DB에만 실행하세요. 기존 DB 변경(migration)은 수행하지 않습니다."""
import asyncio
from database import engine
from database import Base, init_models

async def main():
    init_models()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
