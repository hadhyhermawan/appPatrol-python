import sys
from datetime import datetime
import pytz
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.routers.absensi_legacy_draft import determine_jam_kerja_hari_ini

db = SessionLocal()
now = datetime.now(pytz.timezone('Asia/Jakarta'))
test_date = datetime(2026, 2, 26, 12, 0, 0, tzinfo=pytz.timezone('Asia/Jakarta'))

nik = '1801042008930002'

jam_kerja_obj, presensi = determine_jam_kerja_hari_ini(db, nik, test_date.date(), test_date)

print(f"Untuk tanggal {test_date.date()}:")
if jam_kerja_obj:
    print(f"Jam Kerja: {jam_kerja_obj.nama_jam_kerja} ({jam_kerja_obj.kode_jam_kerja})")
else:
    print("Jam Kerja: None")
