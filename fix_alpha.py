from app.database import SessionLocal
import datetime
from sqlalchemy import text
from app.models.models import Karyawan, Presensi, SetJamKerjaByDay, SetJamKerjaByDate

db = SessionLocal()
date_scan = datetime.date.today() - datetime.timedelta(days=1) # check yesterday

q_active = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1')
active_karyawan = q_active.all()

presensi_list = db.query(Presensi.nik).filter(Presensi.tanggal == date_scan).all()
presensi_niks = {p[0] for p in presensi_list}

potential_absent = [k for k in active_karyawan if k.nik not in presensi_niks]

print(f"Total potential: {len(potential_absent)}")

# Bulk fetch schedules to avoid N+1
hari_indo_map = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis", 4: "Jumat", 5: "Sabtu", 6: "Minggu"}
scan_day_name_indo = hari_indo_map[date_scan.weekday()]

# Query SetJamKerjaByDay
by_day_dict = {}
by_day_list = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.hari == scan_day_name_indo).all()
for b in by_day_list:
    by_day_dict[b.nik] = b.kode_jam_kerja

# Query SetJamKerjaByDate
by_date_dict = {}
by_date_list = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.tanggal == date_scan).all()
for d in by_date_list:
    by_date_dict[d.nik] = d.kode_jam_kerja

holiday_dict = {} # Simplified
# Not checking HariLibur for now just for testing counts

alphas = []
for k in potential_absent:
    has_schedule = False
    if k.nik in by_date_dict:
        has_schedule = True
    elif k.nik in by_day_dict:
        # Check if the code is OFF
        code = by_day_dict[k.nik]
        if code and "OFF" not in code.upper(): # Quick guess
             has_schedule = True
    elif k.kode_jadwal and "OFF" not in k.kode_jadwal.upper():
        has_schedule = True

    if has_schedule:
         alphas.append(k.nik)

print(f"Total True Alphas: {len(alphas)}")
