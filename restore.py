from app.database import SessionLocal
from app.models.models import PatrolSessions
from datetime import datetime, date, time

db = SessionLocal()

records = [
    {
        "id": 8312,
        "nik": "1803101204970002",
        "tanggal": date(2026, 2, 23),
        "jam_patrol": time(16, 8, 7),
        "foto_absen": "1803101204970002-20260223-160807000-absen-patrol.png",
        "kode_jam_kerja": "0003",
        "status": "complete",
        "lokasi_absen": "-4.8397961,104.8795094",
        "created_at": datetime(2026, 2, 23, 23, 8, 7),
        "updated_at": datetime(2026, 2, 23, 18, 6, 19)
    },
    {
        "id": 8359,
        "nik": "1803101204970002",
        "tanggal": date(2026, 2, 23),
        "jam_patrol": time(22, 0, 14),
        "foto_absen": "1803101204970002-20260223-220014000-absen-patrol.png",
        "kode_jam_kerja": "0003",
        "status": "complete",
        "lokasi_absen": "-4.8397961,104.8795094",
        "created_at": datetime(2026, 2, 23, 22, 0, 14),
        "updated_at": datetime(2026, 2, 23, 22, 38, 48)
    },
    {
        "id": 8343,
        "nik": "1803101204970002",
        "tanggal": date(2026, 2, 23),
        "jam_patrol": time(20, 0, 19),
        "foto_absen": "1803101204970002-20260223-200019000-absen-patrol.png",
        "kode_jam_kerja": "0003",
        "status": "complete",
        "lokasi_absen": "-4.8397961,104.8795094",
        "created_at": datetime(2026, 2, 23, 20, 0, 19),
        "updated_at": datetime(2026, 2, 23, 20, 7, 12)
    },
    {
        "id": 8308,
        "nik": "1803101204970002",
        "tanggal": date(2026, 2, 23),
        "jam_patrol": time(16, 1, 18),
        "foto_absen": "1803101204970002-20260223-230118000-absen-patrol.png",
        "kode_jam_kerja": "0003",
        "status": "complete",
        "lokasi_absen": "-4.8397961,104.8795094",
        "created_at": datetime(2026, 2, 23, 23, 1, 18),
        "updated_at": datetime(2026, 2, 23, 23, 8, 5)
    }
]

for rec in records:
    existing = db.query(PatrolSessions).filter(PatrolSessions.id == rec['id']).first()
    if not existing:
        p = PatrolSessions(**rec)
        db.add(p)

db.commit()
print("RESTORED 4 RECORDS.")
