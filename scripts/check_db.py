
import os
import asyncio

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


async def check_db():
    if not DATABASE_URL:
        print("실패: DATABASE_URL이 설정되지 않았습니다.")
        return

    engine = create_async_engine(DATABASE_URL)

    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT current_database()")
            )
            print("연결 성공:", result.scalar())
    except Exception as e:
        print("연결 실패:", type(e).__name__)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_db())
