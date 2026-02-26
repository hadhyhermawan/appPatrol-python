import sys
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import SetJamKerjaByDate
from sqlalchemy import extract

db = SessionLocal()
nik = '1801042008930002'
month = 2
year = 2026

roster_records = db.query(SetJamKerjaByDate).filter(
    SetJamKerjaByDate.nik == nik,
    extract('month', SetJamKerjaByDate.tanggal) == month,
    extract('year', SetJamKerjaByDate.tanggal) == year
).all()

for r in roster_records:
    print(f"{r.tanggal}: {r.kode_jam_kerja}")

