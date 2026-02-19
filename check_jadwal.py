from app.database import SessionLocal
from app.models.models import SetJamKerjaByDate, SetJamKerjaByDay, Karyawan
from datetime import date

db = SessionLocal()
nik = "1801042008930002"
today = date.today() # 2026-02-18

print(f"Checking Jadwal for NIK: {nik} on {today} ({today.strftime('%A')})")

# 1. By Date
by_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today).first()
print(f"1. By Date ({today}): {'FOUND: ' + by_date.kode_jam_kerja if by_date else 'NOT FOUND'}")

# 2. By Day
days_map = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
day_name = days_map[today.weekday()] 
print(f"2. By Day ({day_name}): ", end="")
by_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == day_name).first()
print(f"{'FOUND: ' + by_day.kode_jam_kerja if by_day else 'NOT FOUND'}")

# 3. Karyawan Default
k = db.query(Karyawan).filter(Karyawan.nik == nik).first()
if k:
    print(f"3. Karyawan Default (kode_jadwal): {k.kode_jadwal}")
else:
    print("3. Karyawan NOT FOUND")
