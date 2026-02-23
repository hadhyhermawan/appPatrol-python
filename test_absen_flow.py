import sys
import pytz
from datetime import datetime, timedelta
import requests
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Karyawan, PengaturanUmum, PresensiJamkerja, Presensi, Users
from sqlalchemy import text
from app.routers.auth_legacy import create_android_token

db = SessionLocal()
now = datetime.now(pytz.timezone('Asia/Jakarta'))
today = now.date()
nik = '1801032008930004'

# Bersihkan presensi hari ini
db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today).delete()
db.commit()

# Ambil token
pivot = db.execute(text("SELECT id_user FROM users_karyawan WHERE nik = :nik"), {"nik": nik}).fetchone()
user_id = pivot[0] if pivot else None

if not user_id:
    user = db.query(Users).filter(Users.username == nik).first()
    user_id = user.id

user = db.query(Users).filter(Users.id == user_id).first()
token = create_android_token(data={'sub': str(user.id), 'username': user.username})

url = "http://localhost:8000/api/android/absensi/absen"
headers = {"Authorization": f"Bearer {token}"}
files_masuk = {'image': open('/var/www/appPatrol-python/docs/placeholder.png', 'rb')}
data_masuk = {'status': 'masuk', 'lokasi': '-6.20, 106.81'}

print(f"\n--- TEST ABSEN MASUK [Pukul: {now.strftime('%H:%M:%S WIB')}] ---")
try:
    resp = requests.post(url, data=data_masuk, files=files_masuk, headers=headers)
    print(f"HTTP {resp.status_code}: {resp.text}")
except Exception as e:
    print(f"Request failed: {e}")

# SEKARANG KITA SUSUPKAN DATA PRESENSI SECARA DUMMY UNTUK BISA TEST PULANG!
new_presensi = Presensi(
    nik=nik,
    tanggal=today,
    kode_jam_kerja='0005',
    status='H',
    lintashari=1,
    jam_in=now.replace(hour=15, minute=55, second=0), # Anggap masuk jam 15:55 tadi sore
    foto_in="dummy.jpg",
    lokasi_in="-6.20, 106.81",
    created_at=now,
    updated_at=now
)
db.add(new_presensi)
db.commit()

# Simulate Absen Pulang
print("\n--- TEST ABSEN PULANG [Pukul: {now.strftime('%H:%M:%S WIB')}] ---")
# recreate open file pointer because requests.post closes it
files_pulang = {'image': open('/var/www/appPatrol-python/docs/placeholder.png', 'rb')}
data_pulang = {'status': 'pulang', 'lokasi': '-6.20, 106.81'}

try:
    resp = requests.post(url, data=data_pulang, files=files_pulang, headers=headers)
    print(f"HTTP {resp.status_code}: {resp.text}")
except Exception as e:
    print(f"Request failed: {e}")

# Bersihkan presensi lagi
db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today).delete()
db.commit()

db.close()
