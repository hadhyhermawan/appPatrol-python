import pytest
from datetime import datetime, time, timedelta
import pytz
import sys

# Tambahkan path aplikasi agar bisa import module app
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.routers.absensi_legacy import determine_jam_kerja_hari_ini

def simulate_check_reminder(jam_sekarang: datetime, jam_selesai_shift: datetime, jam_pulang_aktual) -> str:
    """
    Fungsi logika simulasi untuk mengecek apakah notifikasi dikirim atau tidak.
    Aturan: IF (jam_sekarang > jam_selesai_shift) THEN batalkan_notifikasi
    """
    if not jam_pulang_aktual:  # Jika status absen pulang masih kosong (lupa absen)
        if jam_sekarang > jam_selesai_shift:
            return 'Rejected/Suppressed'
        else:
            return 'Send Notification'
    
    return 'Already Clocked Out'

def test_reminder_nik_1801042008930002_shift_malam(capsys):
    """
    Skenario:
    - Karyawan (NIK 1801042008930002)
    - Tanggal data (Check-in start): 2026-02-22
    - Shift Aktif: SF SORE II (16:00 - 08:00) -- lintas hari (berakhir di 2026-02-23 08:00)
    """
    db = SessionLocal()
    tz = pytz.timezone('Asia/Jakarta')
    nik = "1801042008930002"
    
    # Target date schedule
    target_date_str = "2026-02-22"
    tanggal_absen = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    # Pura-puranya ini dijalankan pada 22 Feb sore untuk ambil jadwalnya
    mock_request_time = tz.localize(datetime(2026, 2, 22, 16, 0, 0))
    
    # 1. Ambil data asli dari DB
    jam_kerja_obj, source = determine_jam_kerja_hari_ini(db, nik, tanggal_absen, mock_request_time)
    
    if not jam_kerja_obj:
        pytest.fail(f"Jadwal kerja tidak ditemukan dari source untuk {target_date_str}")
        
    kode_shift = getattr(jam_kerja_obj, 'kode_jam_kerja', 'N/A')
    jam_masuk = jam_kerja_obj.jam_masuk # tipe 'time'
    jam_pulang = jam_kerja_obj.jam_pulang # tipe 'time'
    
    # 2. Perhitungan Shift Lintas Hari (Menangani shift malam)
    shift_start = tz.localize(datetime.combine(tanggal_absen, jam_masuk))
    
    # Jika jam pulang < jam masuk, berarti dia menyeberang ke hari berikutnya (shift malam)
    if jam_pulang < jam_masuk:
        tanggal_pulang = tanggal_absen + timedelta(days=1)
    else:
        tanggal_pulang = tanggal_absen
        
    shift_end = tz.localize(datetime.combine(tanggal_pulang, jam_pulang))
    jam_pulang_aktual = None  # Simulasi Lupa absen
    
    # -- Skenario A: Masih di dalam jam kerja (Misal 23 Februari pukul 04:00 subuh)
    now_dalam_shift = tz.localize(datetime(2026, 2, 23, 4, 0, 0))
    status_dalam = simulate_check_reminder(now_dalam_shift, shift_end, jam_pulang_aktual)
    
    # -- Skenario B: Sudah lewat jam kerja (Misal 23 Februari pukul 09:30 pagi)
    now_lewat_shift = tz.localize(datetime(2026, 2, 23, 9, 30, 0))
    status_lewat = simulate_check_reminder(now_lewat_shift, shift_end, jam_pulang_aktual)

    with capsys.disabled():
        print(f"\n[+] ---- LAPORAN SIMULASI SHIFT MALAM LINTAS HARI ----")
        print(f"     NIK Karyawan      : {nik}")
        print(f"     Jadwal Aktual DB  : {kode_shift} ({jam_masuk} s/d {jam_pulang}) {type(jam_kerja_obj).__name__}")
        print(f"     Shift Mulai       : {shift_start.strftime('%Y-%m-%d %H:%M WIB')}")
        print(f"     Shift Berakhir    : {shift_end.strftime('%Y-%m-%d %H:%M WIB')}")
        print(f"     Data Absen Pulang : KOSONG (Lupa absen)")
        print(f"-------------------------------------------------------")
        print(f"   [Test A] Check di Jam {now_dalam_shift.strftime('%H:%M WIB')} -> {status_dalam} (Harus Send)")
        print(f"   [Test B] Check di Jam {now_lewat_shift.strftime('%H:%M WIB')} -> {status_lewat}  (Harus Suppressed)")
        print(f"-------------------------------------------------------")
        
    assert status_dalam == 'Send Notification', "Gagal! Harus masih mengirim karena masih di jam shift."
    assert status_lewat == 'Rejected/Suppressed', "Gagal! Harus dicegat karena sudah di luar batas shift (08:00) pada hari berikutnya."
