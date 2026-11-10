"""명시적으로 DEMO_SEED=true인 학습 DB에만 샘플을 넣습니다."""
import asyncio
import os
from database import AsyncSessionLocal, engine
from database import init_models
from shared.infrastructure.demo_seed import seed_demo_data

async def main():
    if os.getenv("DEMO_SEED", "false").lower() != "true":
        raise SystemExit("Set DEMO_SEED=true for a dedicated learning database only.")
    init_models()
    async with AsyncSessionLocal() as session:
        await seed_demo_data(session)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
