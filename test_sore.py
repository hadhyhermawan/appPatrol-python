import sys
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Karyawan, SetJamKerjaByDay, PresensiJamkerjaBydept, PresensiJamkerjaBydeptDetail
from sqlalchemy import text

db = SessionLocal()
nik = '1801042008930002'

k = db.query(Karyawan).filter(Karyawan.nik == nik).first()
if not k:
    print("Not found")
    sys.exit()

print(f"Karyawan kode_jadwal default: {k.kode_jadwal}")
print(f"Karyawan dept: {k.kode_dept}, cabang: {k.kode_cabang}")

# 3. Regular Day
regular_records = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik).all()
print("Regular Day:")
for r in regular_records:
    print(f" - Hari: {r.hari}, Kode: {r.kode_jam_kerja}")

# 4. Dept Day
print("Dept Day:")
if k.kode_dept:
    dept_header = db.query(PresensiJamkerjaBydept).filter(
        PresensiJamkerjaBydept.kode_dept == k.kode_dept,
        PresensiJamkerjaBydept.kode_cabang == k.kode_cabang
    ).first()
    if dept_header:
        print(f" Header found: {dept_header.kode_jk_dept}")
        dept_details = db.query(PresensiJamkerjaBydeptDetail).filter(
            PresensiJamkerjaBydeptDetail.kode_jk_dept == dept_header.kode_jk_dept
        ).all()
        for d in dept_details:
            print(f" - Hari: {d.hari}, Kode: {d.kode_jam_kerja}")
    else:
        print(" No Dept header found")

