import asyncio
from datetime import date
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.routers.patroli_legacy import _resolve_jam_kerja_for_date, _build_schedule_tasks_for_day
from app.models.models import Karyawan, Users, Userkaryawan

def test():
    db = SessionLocal()
    nik = "1801042008930002"
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    
    group_niks = [r[0] for r in db.query(Karyawan.nik).filter(
        Karyawan.kode_cabang == karyawan.kode_cabang,
        Karyawan.kode_dept   == karyawan.kode_dept
    ).all()]

    today = date(2026, 2, 21)
    jam_kerja, _ = _resolve_jam_kerja_for_date(nik, karyawan.kode_cabang, karyawan.kode_dept, today, db)
    if jam_kerja:
        print("jam_kerja found:", jam_kerja.kode_jam_kerja)
        tasks = _build_schedule_tasks_for_day(today, jam_kerja, karyawan, group_niks, db)
        print("tasks:", len(tasks))
        if tasks:
            import json
            print(json.dumps(tasks, indent=2))
    else:
        print("No jam kerja")

test()
