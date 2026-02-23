import asyncio
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.models.models import Karyawan, Userkaryawan
from app.routers.patroli_legacy import get_patrol_history, _resolve_jam_kerja_for_date, _build_schedule_tasks_for_day
from datetime import date, timedelta
from app.core.permissions import CurrentUser

db = SessionLocal()

class DummyUser:
    def __init__(self, id):
        self.id = id

async def main():
    nik = "1801042008930003"
    uk = db.query(Userkaryawan).filter(Userkaryawan.nik == nik).first()
    if not uk:
        print("User karyawan not found")
        return
    cu = DummyUser(uk.id_user)
    
    # Test for today and yesterday
    start = (date.today() - timedelta(days=2)).isoformat()
    end = date.today().isoformat()
    
    res = await get_patrol_history(start_date=start, end_date=end, current_user=cu, db=db)
    import json
    print(json.dumps(res, indent=2))

asyncio.run(main())
