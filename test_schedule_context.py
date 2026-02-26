import sys
from datetime import datetime
import pytz
from sqlalchemy import extract
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import SetJamKerjaByDate, SetJamKerjaByDay, PresensiJamkerjaBydept, PresensiJamkerjaBydeptDetail, Karyawan

def determine_base_schedule(db, nik, today):
    # Determine the context of the user's schedule for the current month
    has_roster_this_month = db.query(SetJamKerjaByDate).filter(
        SetJamKerjaByDate.nik == nik,
        extract('month', SetJamKerjaByDate.tanggal) == today.month,
        extract('year', SetJamKerjaByDate.tanggal) == today.year
    ).count() > 0

    has_regular_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik).count() > 0

    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    has_dept_day = False
    dept_map = {}
    if karyawan and karyawan.kode_dept:
        dept_header = db.query(PresensiJamkerjaBydept).filter(
            PresensiJamkerjaBydept.kode_dept == karyawan.kode_dept,
            PresensiJamkerjaBydept.kode_cabang == karyawan.kode_cabang
        ).first()
        if dept_header:
            has_dept_day = db.query(PresensiJamkerjaBydeptDetail).filter(
                PresensiJamkerjaBydeptDetail.kode_jk_dept == dept_header.kode_jk_dept
            ).count() > 0
            
    print(f"Roster month: {has_roster_this_month}")
    print(f"Regular day: {has_regular_day}")
    print(f"Dept day: {has_dept_day}")

db = SessionLocal()
now = datetime.now(pytz.timezone('Asia/Jakarta'))
test_date = datetime(2026, 2, 26, 12, 0, 0, tzinfo=pytz.timezone('Asia/Jakarta'))
nik = '1801042008930002'

determine_base_schedule(db, nik, test_date.date())
