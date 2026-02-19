from app.database import SessionLocal
from app.models.models import SetJamKerjaByDay, SetJamKerjaByDate, PresensiJamkerjaBydeptDetail, Karyawan, PresensiJamkerjaBydept
from sqlalchemy import text
from datetime import date

db = SessionLocal()
tgl = date(2026, 2, 19)
hari = 'Kamis'

print(f"Checking for {tgl} ({hari})...")

try:
    # 1. Check Karyawan
    count_karyawan = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1').count()
    print(f"Active Karyawan: {count_karyawan}")

    # 2. Check SetJamKerjaByDate
    count_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.tanggal == tgl).count()
    print(f"SetJamKerjaByDate: {count_date}")

    # 3. Check SetJamKerjaByDay
    count_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.hari == hari).count()
    print(f"SetJamKerjaByDay for {hari}: {count_day}")

    # 4. Check Dept Detail
    count_dept = db.query(PresensiJamkerjaBydeptDetail).filter(PresensiJamkerjaBydeptDetail.hari == hari).count()
    print(f"PresensiJamkerjaBydeptDetail for {hari}: {count_dept}")
    
    # 5. Check if Dept Parent exists
    count_dept_parent = db.query(PresensiJamkerjaBydept).count()
    print(f"PresensiJamkerjaBydept count: {count_dept_parent}")

    # 6. Check Raw Sample from SetJamKerjaByDay
    raw_day = db.execute(text("SELECT hari FROM presensi_jamkerja_byday LIMIT 1")).fetchone()
    print(f"Sample Hari from DB: {raw_day}")

except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
