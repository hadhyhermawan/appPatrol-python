import os
import sys

# Tambahkan path root agar bisa import module app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, engine, SessionLocal
from app.models.privacy import PrivacyPolicy

# Buat tabel jika belum ada
Base.metadata.create_all(bind=engine, tables=[PrivacyPolicy.__table__])

db = SessionLocal()
print("Checking for existing privacy policies...")
if not db.query(PrivacyPolicy).first():
    sample_content = """# Kebijakan Privasi

Terima kasih telah menggunakan sistem operasional internal perusahaan kami. Kebijakan Privasi ini menjelaskan bagaimana kami mengumpulkan, menggunakan, dan melindungi informasi pribadi Anda selama Anda ("Karyawan") menjalankan tugas lapangan melalui aplikasi seluler ini.

## 1. Pengumpulan Data Identitas
Kami mengumpulkan identitas dasar karyawan (NIK, Nama, Departemen) dan riwayat biometrik wajah (Fitur *Face Master*) yang hanya digunakan murni untuk keperluan konfirmasi data diri saat *Clock In* / *Clock Out*.

## 2. Pengumpulan Data Lokasi dan Kamera
Aplikasi secara aktif merekam data dari dua sensor perangkat Anda:
1. **Lokasi GPS (Latar Belakang):** Kami membutuhkan pelacakan lokasi kontinu (*Background Location*) guna memantau rute pergerakan patroli, validitas kehadiran di titik (*Patrol Point*), serta radius (*geofencing*) yang diwajibkan saat jam dinas operasional berlangsung.
2. **Kamera (Evidence):** Fitur pelaporan (insiden keamanan, kebersihan, pemeriksaan barang) mewajibkan akses kamera untuk mengunggah bukti visual orisinal (*Live Camera Shoot*) yang bebas dari penyuntingan galeri perangkat.

## 3. Penggunaan dan Perlindungan Data
- **Hanya untuk Operasional:** Seluruh pergerakan jejak lokasi dan presensi wajah dikelola mutlak oleh Manajemen Internal, diproses oleh server internal untuk dasar perhitungan KPI Kehadiran dan Kedisiplinan Kinerja (*Payroll*).
- **Enkripsi:** Lalu lintas dan penyimpanan data dilindungi dengan protokol otentikasi ketat berjenjang untuk mencegah penyalahgunaan oleh pihak ketiga. 

## 4. Retensi (Masa Simpan)
Data biometrik Anda dan riwayat koordinat patroli harian akan terus disimpan dalam ekosistem *server* kami untuk rekam audit internal (log), selama Anda masih berstatus aktif sebagai karyawan perusahaan.

## 5. Hubungi Kami
Jika Anda menemukan keraguan atau kejanggalan terhadap permintaan perizinan perangkat (*Permissions*), Anda dapat langsung berkonsultasi dengan Supervisor / Bagian HRD setempat.

Dengan menekan konfirmasi, Anda mengakui bahwa Anda sepenuhnya memahami dan menyetujui pengumpulan dan penggunaan log data GPS dan Biometrik selama jam kerja berjalan.
"""
    new_policy = PrivacyPolicy(
        title="Kebijakan Privasi Keamanan Data Internal",
        content=sample_content,
        version="v1.0.0",
        is_active=True
    )
    db.add(new_policy)
    db.commit()
    print("Seeded new privacy policy.")
else:
    print("Table privacy_policies already has data.")
db.close()
