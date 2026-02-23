from app.database import engine, Base
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.sql import func
from app.database import SessionLocal

class TermsAndConditions(Base):
    __tablename__ = 'terms_and_conditions'
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# Create table if not exists
Base.metadata.create_all(bind=engine, tables=[TermsAndConditions.__table__])

# Seed data
db = SessionLocal()
if not db.query(TermsAndConditions).first():
    sample_content = """# Syarat & Ketentuan Penggunaan Aplikasi

Selamat datang di Sistem Manajemen Kepatuhan dan Keamanan Operasional. Dengan mengakses dan menggunakan aplikasi ini, Anda ("Pengguna") menyetujui untuk terikat dengan Syarat & Ketentuan berikut.

## 1. Penggunaan Aplikasi
Aplikasi ini ditujukan secara eksklusif bagi karyawan internal, termasuk staf operasional, petugas keamanan (security), staf kebersihan (cleaning service), dan staf logistik untuk memfasilitasi pelaporan kehadiran, jadwal kerja, patroli keamanan, serta tugas operasional lainnya.

## 2. Keamanan dan Data Pribadi
1. **Identitas Diri:** Anda wajib menggunakan NIK dan password yang sah. Segala aktivitas di bawah akun Anda sepenuhnya menjadi tanggung jawab Anda.
2. **Data Lokasi (GPS):** Aplikasi membutuhkan akses lokasi berkelanjutan (*background location*) untuk mengautentikasi aktivitas patroli dan absensi berbasis radius geografis. Lokasi fisik Anda dicatat dan disimpan untuk keperluan kepatuhan kerja.
3. **Data Biometrik:** Modul *Face Master* menyimpan rekam wajah untuk mencegah kecurangan *clock-in*/absensi, dikelola secara terpusat oleh sistem.
4. **Manipulasi Sistem:** Segala upaya mengakali perangkat GPS lokal (seperti aplikasi *Fake GPS*), melakukan pemblokiran memori, maupun memodifikasi akses server merupakan tindakan pelanggaran berat yang akan dicatat dan dilaporkan otomatis ke sistem manajemen pelanggaran.

## 3. Kewajiban Operasional
- Seluruh sesi absensi dan patroli harus diselesaikan dengan wajar sesuai Standard Operating Procedure (SOP).
- Pengguna wajib menaati batas radius area yang dialokasikan dan melampirkan foto laporan (*evidence*) yang jujur tanpa penyuntingan.
- Kerahasiaan data perusahaan, informasi klien operasional, maupun pelaporan sistem terproteksi dan tidak boleh diekspor ke sistem/entitas di luar kewenangan aplikasi.

## 4. Konsekuensi Pelanggaran (Penalty)
Sistem memiliki mekanisme keamanan berjenjang (*Live Scanning*). Jika sistem mendeteksi bentuk kecurangan seperti *Mock Location*, penutupan paksa aplikasi sewaktu patroli (*Force Close*), dan manipulasi rute radius, maka sistem akan:
1. Mengunci perangkat untuk sesi tersebut (*Device Lock*).
2. Mengekstrak notifikasi pelanggaran seketika (FCM) ke supervisor.
3. Mencatat rapor pelanggaran secara otomatis pada matriks KPI (Key Performance Indicator).

## 5. Pembaruan dan Modifikasi
Manajemen berhak sesekali memperbarui Syarat & Ketentuan sesuai perkembangan regulasi IT perusahaan. Segala penyesuaian akan segera menginisasi pembaharuan di layar ini dan memberlakukan pembaruan wajib.

Dengan melakukan konfirmasi absensi dan rutinitas kerja, Anda kami anggap telah membaca dan tunduk pada seluruh syarat dan ketentuan sistem operasional pengamanan dan pelaporan ini.
"""
    new_terms = TermsAndConditions(
        title="Syarat & Ketentuan Internal",
        content=sample_content,
        version="v1.0.0",
        is_active=True
    )
    db.add(new_terms)
    db.commit()
    print("Seeded new terms.")
else:
    print("Table already has data.")
db.close()
