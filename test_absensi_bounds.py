import sys
import pytz
from datetime import datetime, timedelta
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Karyawan, PengaturanUmum, PresensiJamkerja, Presensi
db = SessionLocal()
now = datetime.now(pytz.timezone('Asia/Jakarta'))
nik = '1801032008930004'

karyawan_check = db.query(Karyawan).filter(Karyawan.nik == nik).first()
setting = db.query(PengaturanUmum).first()
today = now.date()
WIB = pytz.timezone('Asia/Jakarta')

print("Mocked API Calls (Now = {})".format(now))

jk = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == '0005').first()

# Logic Kunci Jam Kerja (Bounds) untuk Masuk
if karyawan_check and str(karyawan_check.lock_jam_kerja) == '1' and setting and str(setting.batasi_absen) == '1' and jk:
    batas_absen = int(setting.batas_jam_absen) if setting.batas_jam_absen else 0
    jadwal_masuk_str = f"{today.strftime('%Y-%m-%d')} {jk.jam_masuk.strftime('%H:%M:%S')}"
    jadwal_masuk = datetime.strptime(jadwal_masuk_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=WIB)
    batas_akhir_masuk = jadwal_masuk + timedelta(hours=batas_absen)
    batas_awal_masuk = jadwal_masuk - timedelta(hours=3) # Allow 3 hours early max
    
    print('jadwal_masuk', jadwal_masuk)
    print('batas_akhir_masuk', batas_akhir_masuk)
    print('batas_awal_masuk', batas_awal_masuk)
    
    if now > batas_akhir_masuk:
        print("EXCEPTION 403: Batas waktu absen masuk berakhir.")
    if now < batas_awal_masuk:
        print("EXCEPTION 403: Belum waktunya absen masuk.")

presensi = db.query(Presensi).filter(Presensi.nik == '1801032008930004', Presensi.tanggal == '2026-02-22').first()
# Logic Kunci Jam Kerja (Bounds) untuk Pulang
if karyawan_check and str(karyawan_check.lock_jam_kerja) == '1' and setting and str(setting.batasi_absen) == '1':
    jk_pulang = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == presensi.kode_jam_kerja).first()
    if jk_pulang:
        batas_absen_pulang = int(setting.batas_jam_absen_pulang) if setting.batas_jam_absen_pulang else 0
        jadwal_pulang_str = f"{presensi.tanggal.strftime('%Y-%m-%d')} {jk_pulang.jam_pulang.strftime('%H:%M:%S')}"
        jadwal_pulang = datetime.strptime(jadwal_pulang_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=WIB)
        
        if str(jk_pulang.lintashari) == '1':
            jadwal_pulang = jadwal_pulang + timedelta(days=1)
            
        batas_akhir_pulang = jadwal_pulang + timedelta(hours=batas_absen_pulang)
        print('jadwal_pulang', jadwal_pulang)
        print('batas_akhir_pulang', batas_akhir_pulang)
        
        if now > batas_akhir_pulang:
            print("EXCEPTION 403: Batas waktu absen pulang berakhir.")
