import asyncio
from app.database import SessionLocal
from app.routers.patroli_legacy import _build_schedule_tasks_for_day
from app.routers.absensi_legacy import determine_jam_kerja_hari_ini
from app.models.models import Karyawan, Userkaryawan
from datetime import date, timedelta, datetime
from app.routers.auth_legacy import CurrentUser

async def test():
    db = SessionLocal()
    # Find a user with jam_kerja
    karyawan = db.query(Karyawan).filter(Karyawan.nik == "1801042008930005").first()
    if not karyawan: return
    nik = karyawan.nik

    print(f"Testing for NIK: {nik}")
    
    group_niks = [
        r[0] for r in db.query(Karyawan.nik).filter(
            Karyawan.kode_cabang == karyawan.kode_cabang,
            Karyawan.kode_dept   == karyawan.kode_dept
        ).all()
    ]
    
    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    tasks = []
    current_day = start
    now_wib = datetime.now()
    while current_day <= end:
        jam_kerja, _ = determine_jam_kerja_hari_ini(db, nik, current_day, now_wib)
        if jam_kerja:
            print(f"[{current_day}] jam_kerja found: {jam_kerja.kode_jam_kerja}")
            day_tasks = _build_schedule_tasks_for_day(current_day, jam_kerja, karyawan, group_niks, db)
            print(f"[{current_day}] generated {len(day_tasks)} tasks")
            tasks.extend(day_tasks)
        else:
            print(f"[{current_day}] no jam_kerja")
        current_day += timedelta(days=1)
        
    print(f"Total tasks: {len(tasks)}")
    if len(tasks) > 0:
        print(tasks[0])

asyncio.run(test())
