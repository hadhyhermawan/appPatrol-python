# Dokumentasi Migrasi AppPatrol (Next.js + Python FastAPI)

Dokumen ini merangkum progress pengembangan sistem admin baru AppPatrol yang menggunakan teknologi modern **Next.js (Frontend - TailAdmin Template)** dan **Python FastAPI (Backend)**, menggantikan atau berjalan berdampingan dengan sistem Laravel yang lama.

## 1. Informasi Server & Akses

Berikut adalah detail konfigurasi server dan port untuk menjalankan aplikasi:

| Komponen | Teknologi | Path Direktori | Port | URL Akses |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend** | Next.js 16, Tailwind CSS (TailAdmin) | `/var/www/apppatrol-admin` | **3001** | [http://localhost:3001](http://localhost:3001) |
| **Backend** | Python FastAPI, SQLAlchemy | `/var/www/appPatrol-python` | **8000** | [http://localhost:8000](http://localhost:8000) |
| **API Docs** | Swagger UI | - | 8000 | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Storage** | Laravel Storage (Mounted) | `/var/www/appPatrol/storage` | 8000 | `http://localhost:8000/storage/...` |

---

## 2. Fitur yang Sudah Diselesaikan

### A. Dashboard Utama (`/`)
*   **Statistik Real-time**: Menampilkan jumlah karyawan Hadir, Terlambat, dan Tidak Hadir hari ini.
*   **Live Clock**: Penunjuk waktu dan tanggal dinamis.
*   **Quick Actions**: Pintasan ke menu Presensi dan Karyawan.

### B. Monitoring Presensi (`/presensi`)
*   **Tabel Monitoring**: Menampilkan data presensi harian dengan detail Foto (Masuk/Keluar), Jam, Lokasi, dan Status Kehadiran.
*   **Filter Canggih**:
    *   **Filter Tanggal**: Bisa pilih tanggal spesifik atau "Semua Hari".
    *   **Filter Departemen**: Dropdown filter unit kerja.
*   **Pagination**: Server-side pagination untuk menangani ribuan data dengan cepat.
*   **Data Sinkron**: Data diambil langsung dari database utama yang sama dengan Laravel.

### C. Master Karyawan (`/master/karyawan`)
*   **Replikasi Tabel Laravel**: Tabel lengkap dengan **28+ Kolom** (Informasi Pribadi, Kontak, Dokumen, Status, dll).
*   **Fitur Khusus**:
    *   **Masa Aktif KTA**: Badge otomatis (Hijau/Kuning/Merah) untuk memantau masa berlaku KTA Satpam.
    *   **WhatsApp Link**: Klik ikon smartphone untuk langsung chat WA ke karyawan.
    *   **Action Icons**: Ikon untuk Set Jam Kerja, Edit, Lock Location, Lock Device, dll.
    *   **Horizontal Scroll**: Menangani tampilan data yang sangat lebar dengan rapi.
*   **Integrasi Foto/Dokumen**: Foto Profil, KTP, dan Ijazah diambil dari folder storage Laravel yang di-*mount* ke server Python.

---

## 3. Struktur Folder & File Penting

### A. Backend (`/var/www/appPatrol-python`)
Fokus pada logika bisnis, query database, dan API.

*   `app/`
    *   `main.py`: **Entry Point**. Konfigurasi CORS, dan *Mounting* folder Storage Laravel agar gambar bisa diakses.
    *   `database.py`: Konfigurasi koneksi ke Database MySQL.
    *   `models/`
        *   `models.py`: Definisi Table (ORM) seperti `Karyawan`, `Presensi`, `Departemen`, dll.
    *   `routers/`:
        *   `dashboard.py`: API untuk statistik dashboard.
        *   `monitoring.py`: API untuk data presensi dan filter.
        *   `master.py`: API untuk CRUD karyawan, filter options, dan logika masa aktif anggota.

### B. Frontend (`/var/www/apppatrol-admin`)
Fokus pada tampilan (UI/UX) dan interaksi user.

*   `src/app/`
    *   `page.tsx`: Halaman Dashboard.
    *   `presensi/page.tsx`: Halaman Monitoring Presensi.
    *   `master/karyawan/page.tsx`: Halaman Master Karyawan (Tabel Besar).
*   `src/components/`
    *   `layout/`: Komponen Sidebar, Header, dan Main Layout.
*   `src/lib/`
    *   `api.ts`: Konfigurasi Axios Client (Base URL ke port 8000).

---

## 4. Cara Menjalankan Aplikasi

Untuk melanjutkan pengembangan, Anda perlu menjalankan **dua terminal** terpisah:

**Terminal 1: Menjalankan Frontend (Next.js)**
```bash
cd /var/www/apppatrol-admin
export PORT=3001
npm run dev
```

**Terminal 2: Menjalankan Backend (Python)**
```bash
cd /var/www/appPatrol-python
source .venv/bin/activate
python3 app/main.py
```

Setelah keduanya jalan, buka browser di **[http://localhost:3001](http://localhost:3001)**.

---

## 5. Ekosistem Aplikasi & Integrasi

Aplikasi ini tidak berdiri sendiri, melainkan bagian dari ekosistem yang lebih besar:

### A. Backend Utama (Laravel)
*   **Path**: `/var/www/appPatrol`
*   **Peran**: API Utama untuk Aplikasi Android (`GuardSystemApp`), Autentikasi (Sanctum), dan Logika Bisnis Legacy.
*   **Endpoint API**: Hampir seluruh endpoint Android (`/api/login`, `/api/absensi`, `/api/patroli`) dilayani oleh Laravel ini.
*   **Koneksi**: Berbagi database MySQL yang sama dengan Backend Python.

### B. Backend Python (Service Tambahan)
*   **Path**: `/var/www/appPatrol-python`
*   **Peran**:
    *   API untuk Dashboard Admin Baru (Next.js).
    *   Komputasi berat / AI (jika ada, misal Face Recognition lanjutan).
    *   Statistik & Monitoring Real-time.
*   **Integrasi**: Python mengakses Database MySQL secara langsung (SQLAlchemy) tanpa melalui API Laravel.

### C. Layanan Real-time & Komunikasi

Sistem ini menggunakan dua layanan Node.js terpisah untuk kebutuhan komunikasi yang berbeda:

1.  **Push To Talk (Walkie Talkie Audio)**
    *   **Path**: `/var/www/PushToTalkServer`
    *   **Port**: 8081
    *   **Teknologi**: WebSocket (`ws` library) + Node.js.
    *   **Fungsi**: Menangani broadcast audio satu arah (half-duplex) antar pengguna dalam satu channel/room.
    *   **Validasi**: Memverifikasi token user ke Laravel API (`/api/walkie/user`).

2.  **WebRTC Signaling (Video Call / P2P)**
    *   **Path**: `/var/www/walkieWebRTC`
    *   **Port**: 3005
    *   **Teknologi**: Socket.IO + Express.
    *   **Fungsi**: Bertindak sebagai *signaling server* untuk memfasilitasi koneksi Peer-to-Peer (WebRTC) antar perangkat (misal untuk Video Call).

### D. Aplikasi Android (GuardSystemApp)
*   **Source Code**: `/var/www/GuardSystemApp-src`
### E. Service Verifikasi Wajah (Python API Khusus)
*   **Path**: `/var/www/appPatrol/deteksiwajah-api`
*   **Port**: 5000 (Flask / Gunicorn)
*   **Teknologi**: Python, Flask, DeepFace (ArcFace).
*   **Fungsi**: Melakukan pencocokan foto selfie (saat absen/patroli) dengan foto referensi karyawan yang tersimpan.
*   **Alur Kerja**: Android kirim foto ke Laravel -> Laravel kirim foto ke Service ini -> Service mengembalikan hasil (Match/Not Match).

## 6. Absensi Mobile & Timezone (Update Feb 2026)

### A. Endpoint `/api/android/absensi/hariini` (Legacy Python)
Endpoint ini telah di-rewrite untuk mendukung Aplikasi Android `GuardSystemApp` secara native tanpa melalui Laravel, menggantikan endpoint lama.

**Perubahan Pinting:**
1.  **Struktur Flat JSON**: Response disesuaikan sepenuhnya dengan model `AbsensiResponse.kt` di Android. Data dikirim dalam format flat (misal: `wajah_terdaftar`, `jam_masuk`, `lock_jam_kerja` langsung di root `data`), bukan nested object `presensi` dan `jam_kerja`.
2.  **Timezone Fixing**: Backend Python dipaksa menggunakan Timezone `Asia/Jakarta` (WIB) via library `pytz` untuk semua operasi tanggal dan jam. Ini mengatasi masalah perbedaan hari antara Server (UTC) dan User (WIB) pada jam 00:00-07:00, yang sebelumnya menyebabkan jadwal "Kemarin" terbaca atau jadwal "Besok" tidak terbaca.
3.  **Smart Schedule Lookup**:
    *   Sistem otomatis mencari jadwal kerja aktif berdasarkan prioritas: **Tanggal Khusus (`presensi_jamkerja_bydate`)** -> **Hari Mingguan (`presensi_jamkerja_byday`)** -> **Default Karyawan (`karyawan.kode_jadwal`)**.
    *   Jadwal kerja kini **selalu muncul** meskipun user **belum melakukan absen** (sebelumnya jadwal menghilang jika presensi nol, membuat UI Android bingung).

### B. Dependencies Baru
Backend Python kini membutuhkan library berikut agar fitur Absensi dan Timezone berjalan normal:
*   `pytz`: Library wajib untuk menangani Timezone Asia/Jakarta.
*   `python-socketio[asyncio]`: Library tambahan untuk event socket (jika diperlukan di masa depan).

**Catatan:** Pastikan library ini terinstall di dalam virtual environment (`.venv`) server produksi, agar tidak terjadi error "502 Bad Gateway" atau "Module Not Found".

## 7. Pembaruan Sistem Autentikasi & Role (Feb 2026)

### A. Autentikasi JWT (Python Backend)
Backend Python kini telah meninggalkan penggunaan *Dummy User* (Hardcoded ID 1) dan beralih sepenuhnya ke **Validasi Token JWT**.
- **File**: `app/routers/role_permission.py` dan `app/routers/auth_legacy.py`.
- **Mekanisme**: Token Bearer dari header Authorization di-decode menggunakan `SECRET_KEY` yang sama dengan Laravel.
- **Dampak**: API endpoint yang sensitif (`/roles`, `/users`, `/permissions`) kini aman dan hanya bisa diakses oleh user yang memiliki token valid dan permission yang sesuai.

### B. Manajemen Role & Permission
- **Format Role**: Endpoint `/utilities/users` kini secara otomatis memformat nama role menjadi **Title Case** (misal: "Super Admin") dan memprioritaskan role tertinggi untuk ditampilkan di Frontend. Ini memperbaiki bug badge role yang tidak muncul.
- **Konsistensi Data**: Backend memastikan bahwa data role yang dikirim ke Frontend sesuai dengan yang tersimpan di database `model_has_roles`.

### C. Kompatibilitas Next.js 15+ (Frontend)
- **Async Params**: Halaman dinamis seperti `master/karyawan/show/[nik]` telah diperbarui menggunakan `React.use()` untuk menangani parameter URL, sesuai dengan standar baru Next.js 15.
- **Validasi Ketat**: Penanganan error `500 Internal Server Error` akibat parameter `undefined` telah diperbaiki di kedua sisi (Frontend & Backend).

## 8. Manajemen File & Dokumen (Feb 2026)

### A. Struktur Folder Penyimpanan (Laravel Compatibility)
Backend Python kini menyimpan dan membaca file langsung dari direktori penyimpanan utama Laravel (`/var/www/appPatrol/storage/app/public/karyawan`) untuk memastikan kompatibilitas penuh dengan sistem lama dan akses URL publik.

**Mapping Folder:**
- **Foto Profil**: Root folder `karyawan/`
- **KTP**: Subfolder `karyawan/ktp/`
- **Kartu Anggota**: Subfolder `karyawan/kartu/` (*Bukan `kartu_anggota`*)
- **Ijazah**: Subfolder `karyawan/ijazah/`
- **SIM**: Subfolder `karyawan/sim/`

### B. Master Wajah (Face Recognition)
Disimpan di `storage/app/public/uploads/facerecognition/{NIK}-{NAMA_DEPAN}/`.
- Backend Python (`master.py`) dan (`master_wajah_legacy.py`) secara otomatis menangani pembentukan URL dinamis dan pembuatan folder berdasarkan pola nama ini.

### C. Logika Upload (`master.py`)
Fungsi `save_upload` dan endpoint `create/update` karyawan telah diperbarui untuk:
1.  Menyimpan file fisik ke **Path Absolut** Laravel Storage.
2.  Menggunakan nama subfolder yang benar (`kartu` alih-alih `kartu_anggota`).
3.  Ini mencegah file tersimpan di penyimpanan lokal Python yang tidak dapat diakses publik.

---

## 9. Update Perbaikan Sistem (19 Februari 2026)

### A. Kompatibilitas Backend (Pydantic V1 vs V2)
Ditemukan konflik versi Pydantic antara environment development (V1) dan produksi PM2 (V2), yang menyebabkan **Error 500** pada endpoint monitoring.

**Solusi Hybrid:**
Semua Data Transfer Object (DTO) di `security.py` dan `berita.py` kini menggunakan konfigurasi ganda:
```python
class Config:
    from_attributes = True  # Mandatory untuk Pydantic V2
    orm_mode = True         # Mandatory untuk Pydantic V1
```
Metode validasi dikembalikan ke `from_orm()` yang didukung kedua versi tersebut.

### B. Mekanisme Keamanan Data (Patrol)
Frontend kini lebih tangguh terhadap data korup. Di backend, loop pemrosesan data patroli (`get_patrol_list`) dilengkapi blok `try-except`. Jika satu baris data gagal diproses (misal format tanggal salah), data tersebut akan **dilewati (skip)** dan dicatat di log, sementara sisa data yang valid tetap dikirim ke Frontend.

### C. Integrasi Storage Berita
Modul Berita kini terintegrasi penuh dengan ekosistem Laravel:
1.  **Lokasi Upload**: File berita yang diunggah via Python Backend kini disimpan langsung ke `/var/www/appPatrol/storage/app/public/uploads/berita`, folder yang sama dengan Laravel.
2.  **Base URL**: Konfigurasi `.env` diperbarui menjadi `BASE_URL=https://frontend.k3guard.com/api-py`, memastikan semua URL gambar (Berita, Karyawan, dll) dilayani melalui endpoint Python yang benar.

### D. Perbaikan Frontend (UI/UX)
1.  **Foto Bulat & Preview**: Tampilan foto absen di halaman **Patrol** dan **Presensi** diseragamkan menjadi bentuk lingkaran (`rounded-full`) dan dilengkapi fitur klik untuk memperbesar foto (Modal Preview).
2.  **Fix Data Binding**: Memperbaiki bug di halaman Berita dimana field `foto` kosong karena backend mengirim key `foto_url`. Frontend kini membaca key yang benar.

### E. Fitur Baru: Monitoring Regu (Security Teams)
Halaman `/security/teams` kini memiliki fitur **Monitoring Regu** yang visual dan interaktif, meniru fungsi legacy `monitoring-regu`.

1.  **Dual View**: Pengguna dapat beralih antara "Monitoring Harian" untuk memantau kehadiran, dan "Kelola Jadwal" untuk mengatur shift.
2.  **Smart Schedule Mapping**: Backend backend secara otomatis memetakan karyawan ke regu patroli yang tepat berdasarkan hierarki jadwal (Override Tanggal > Override Hari > Jadwal Default).
3.  **Status Kehadiran**: Menampilkan status Real-time (Hadir/Belum), jam masuk/pulang, serta foto bukti kehadiran langsung di dalam kartu regu.

### E. (Revisi) Fitur Monitoring Regu
Revisi logika monitoring agar sesuai dengan dashboard Laravel asli (Patrol Focused):
1.  **Patroli vs Absensi**: Fokus utama adalah kepatuhan patroli (`PatrolSessions`), bukan hanya kehadiran kerja.
2.  **Hourly Monitoring**: Visualisasi slot per jam (Hijau = Patroli Dilakukan, Merah = Terlewat).
3.  **Smart Grouping**: Mengelompokkan regu berdasarkan jadwal kerja dinamis (Date > Day > Dept) dan mengecek kepatuhan anggota terhadap jadwal tersebut.

## 10. Pembaruan Modul Security (Surat & Tamu) - 19 Februari 2026

### A. Standardisasi UI/UX (Surat & Tamu)
Halaman `/security/surat` dan `/security/tamu` telah diperbarui total untuk mengikuti standar desain aplikasi yang modern dan konsisten (mengikuti gaya halaman Patrol dan Presensi).

1.  **Desain Konsisten**:
    *   **Layout Card**: Data ditampilkan dalam tabel yang bersih di dalam card container.
    *   **Rounded Images**: Foto surat dan tamu kini ditampilkan dalam bentuk lingkaran (`rounded-full`) dengan border putih, seragam dengan halaman lainnya.
    *   **Status Badges**: Penggunaan badge warna-warni untuk status surat dan tamu.

2.  **Fitur Baru Frontend**:
    *   **Tab Interface (Surat)**: Pemisahan data "Surat Masuk" dan "Surat Keluar" menggunakan tab navigasi yang responsif.
    *   **Advanced Filter**: Penambahan filter rentang tanggal (**Dari Tanggal** - **Sampai Tanggal**) dan pencarian teks (**Search**) di kedua halaman.
    *   **Image Preview**: Klik pada thumbnail foto akan membuka modal *lightbox* untuk melihat gambar ukuran penuh.
    *   **Enhanced Form Modal**:
        *   **DatePicker**: Input tanggal/waktu yang lebih akurat.
        *   **SearchableSelect**: Pemilihan petugas satpam dengan fitur pencarian.

### B. Backend Enhancements (`security.py`)
Backend Python telah diperbarui untuk mendukung fitur-fitur baru di frontend dan memperbaiki masalah tampilan data.

1.  **Automatic Image URL Prefixing**:
    *   Endpoint `get_surat_masuk`, `get_surat_keluar`, dan `get_tamu` kini memiliki logika otomatis untuk menambahkan prefix `STORAGE_BASE_URL` (dari env) ke field `foto`, `foto_penerima`, dan `foto_keluar`.
    *   **Manfaat**: Ini memastikan URL gambar selalu valid dan dapat diakses oleh frontend tanpa perlu manipulasi string manual di sisi klien.

2.  **Date Range Filtering**:
    *   API Endpoint kini menerima parameter query `date_start` dan `date_end`.
    *   Backend melakukan filtering query database berdasarkan rentang tanggal yang diberikan, memungkinkan user mencari data arsip dengan mudah.
