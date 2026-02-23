import sys
import pytz
from datetime import datetime, timedelta
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Karyawan, PengaturanUmum, PresensiJamkerja, Presensi, Users
from sqlalchemy import text
from app.routers.auth_legacy import create_android_token
from app.routers.absensi_legacy import determine_jam_kerja_hari_ini

db = SessionLocal()
now = datetime.now(pytz.timezone('Asia/Jakarta'))
today = now.date()
nik = '1801042008930002'

karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
if not karyawan:
    print("Karyawan not found")
    sys.exit()

print(f"Karyawan: {karyawan.nama_karyawan}, lock_jam_kerja: {karyawan.lock_jam_kerja}")

setting = db.query(PengaturanUmum).first()
print(f"batasi_absen: {setting.batasi_absen}, batas_jam_absen: {setting.batas_jam_absen}, batas_jam_absen_pulang: {setting.batas_jam_absen_pulang}")

jam_kerja_obj, source = determine_jam_kerja_hari_ini(db, nik, today, now)
if jam_kerja_obj:
    print(f"Jam Kerja: {jam_kerja_obj.kode_jam_kerja} ({jam_kerja_obj.jam_masuk} - {jam_kerja_obj.jam_pulang}) {source}")
    batas_absen = int(setting.batas_jam_absen) if setting.batas_jam_absen else 0
    jadwal_masuk_str = f"{today.strftime('%Y-%m-%d')} {jam_kerja_obj.jam_masuk.strftime('%H:%M:%S')}"
    jadwal_masuk = datetime.strptime(jadwal_masuk_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.timezone('Asia/Jakarta'))
    batas_akhir_masuk = jadwal_masuk + timedelta(hours=batas_absen)
    batas_awal_masuk = jadwal_masuk - timedelta(hours=3) # Allow 3 hours early max

    if now > batas_akhir_masuk:
        print("-> Status Absen Masuk: Batas waktu absen masuk berakhir.")
    elif now < batas_awal_masuk:
        print("-> Status Absen Masuk: Belum waktunya absen masuk.")
    else:
        print("-> Status Absen Masuk: Waktu absen valid.")
else:
    print("Jam Kerja: Tidak ditemukan/NS")

# Find user id to get token
pivot = db.execute(text("SELECT id_user FROM users_karyawan WHERE nik = :nik"), {"nik": nik}).fetchone()
if not pivot:
    print("Pivot not found, trying username")
    user = db.query(Users).filter(Users.username == nik).first()
    if user:
        user_id = user.id
    else:
        print("User not found")
        sys.exit()
else:
    user_id = pivot[0]
user = db.query(Users).filter(Users.id == user_id).first()
token = create_android_token(data={'sub': str(user.id), 'username': user.username})

print("\nCoba CURL ke API secara langsung (Simulasi Aplikasi):")
import os
import requests
url = "http://localhost:8000/api/android/absensi/absen"
headers = {"Authorization": f"Bearer {token}"}
files = {'image': open('/var/www/appPatrol-python/docs/placeholder.png', 'rb')}
data = {'status': 'masuk', 'lokasi': '-6.20, 106.81'}
try:
    resp = requests.post(url, data=data, files=files, headers=headers)
    print(f"HTTP {resp.status_code}: {resp.text}")
except Exception as e:
    print(f"Request failed: {e}")

