import asyncio
from app.database import SessionLocal
try:
    from app.routers.security import get_patrol_list
except ImportError:
    pass
import traceback
from datetime import date

async def main():
    try:
        db = SessionLocal()
        print("Calling get_patrol_list with limit 100...")
        result = await get_patrol_list(
            search=None,
            date_start=None,
            date_end=None,
            limit=100,
            db=db
        )
        print("Success!")
        print(f"Results: {len(result)}")
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
