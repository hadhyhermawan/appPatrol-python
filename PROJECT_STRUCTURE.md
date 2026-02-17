# Struktur Lengkap Project AppPatrol & Dokumentasi Teknis

Dokumen ini menjelaskan arsitektur sistem AppPatrol yang terdiri dari **tiga komponen utama**: Backend Legacy (Laravel), Backend Modern (Python FastAPI), dan Admin Dashboard (Next.js), yang semuanya terhubung melalui satu **Database Pusat**.

---

## 1. Arsitektur Sistem Terintegrasi

Sistem AppPatrol menggunakan pendekatan **Shared Database Architecture**, di mana aplikasi lama (Laravel) dan aplikasi baru (Python/Next.js) menggunakan database yang sama secara real-time.

```mermaid
graph TD
    A[Admin Dashboard (Next.js)] -->|REST API| B(Backend Python FastAPI)
    C[Web Admin Lama (Laravel)] <-->|Internal Logic| D[(Database MySQL: 'patrol')]
    B <-->|ORM SQLAlchemy| D
    B -->|Read-only| E[Laravel Storage (Foto/Dokumen)]
```

### Komponen Utama:
1.  **Database ('patrol')**: Jantung sistem. Menyimpan semua data karyawan, presensi, dan konfigurasi.
2.  **Backend Legacy (Laravel)**: Sistem inti yang menangani input data awal, manajemen user, dan operasional harian lama.
3.  **Backend Modern (Python)**: Layer API cepat untuk fitur monitoring real-time, dashboard analitik, dan tabel master canggih.
4.  **Frontend Modern (Next.js)**: Antarmuka admin baru yang responsif dan interaktif.

---

## 2. Struktur Database (MySQL)

Database bernama **`patrol`** digunakan bersama oleh kedua backend. Berikut adalah tabel-tabel kunci dan fungsinya:

### Tabel Master Data
*   `karyawan`: Tabel utama biodata (NIK, Nama, Kontak, Status).
    *   *Kolom Kunci*: `nik`, `nama_karyawan`, `kode_dept`, `kode_jabatan`, `kode_cabang`.
    *   *Dokumen*: `foto`, `foto_ktp`, `no_ijazah` (Satpam), `no_sim` (Driver).
*   `departemen`: Unit kerja (`UK3`=Security, `UCS`=Cleaning Service, `UDV`=Driver).
*   `jabatan`: Posisi/jabatan (`DNR`=Danru, `KRD`=Koordinator, `CSV`=CS Supervisor).
*   `cabang`: Lokasi kerja/site.
*   `users`: Akun login untuk aplikasi mobile dan web.

### Tabel Operasional
*   `presensi`: Data absen harian (Clock In/Out, Foto Wajah, Lokasi GPS).
*   `jadwal_kerja`: Shift kerja karyawan.
*   `patroli`: (Khusus Security) Log kegiatan patroli area.

---

## 3. Backend Legacy (Laravel Framework)

Ini adalah aplikasi web asli yang sudah berjalan (*existing system*). Backend Python "menumpang" pada struktur data yang dibuat oleh Laravel ini.

**Lokasi**: `/var/www/appPatrol`
**Framework**: Laravel (PHP)

**Struktur Penting:**
*   `app/Models/`: Definisi Eloquent ORM (Sumber kebenaran struktur database).
    *   `Karyawan.php`, `Presensi.php`, `User.php`.
*   `app/Http/Controllers/`: Logika bisnis web admin lama.
    *   `KaryawanController.php`: Menangani CRUD karyawan lama.
    *   `PresensiController.php`: Menangani laporan presensi lama.
*   `storage/app/public/`: **Penyimpanan File Fisik**.
    *   Semua foto (Profil, KTP, Absen) disimpan di sini.
    *   Backend Python me-*mount* folder ini agar bisa diakses oleh Next.js.
*   `.env`: Konfigurasi Database Utama (`DB_DATABASE=patrol`).

---

## 4. Backend Modern (Python FastAPI)

Backend ini dibangun sebagai *Extension* untuk fitur-fitur yang membutuhkan performa tinggi (Real-time monitoring) atau UI yang lebih modern.

**Lokasi**: `/var/www/appPatrol-python`
**Framework**: FastAPI (Python)

**Struktur:**
*   `app/models/models.py`: Replikasi struktur tabel Laravel menggunakan SQLAlchemy agar Python bisa membaca/tulis ke database yang sama.
*   `app/routers/`: Endpoint API baru.
    *   `master.py`: Endpoint canggih untuk tabel Karyawan (Filter lengkap, Pagination cepat).
    *   `monitoring.py`: Endpoint untuk Dashboard Real-time.
*   `main.py`: Mengatur CORS dan *Mounting* folder `storage` Laravel.

**Fitur Unggulan:**
*   **Kecepatan**: Respon API JSON sangat cepat untuk data besar.
*   **Analitik**: Perhitungan otomatis (misal: Sisa Masa Aktif KTA Satpam).

---

## 5. Frontend Modern (Next.js)

Antarmuka Admin baru yang dibangun menggunakan **TailAdmin Free Next.js Admin Dashboard Template**. Tampilannya lebih *fresh*, responsif, dan interaktif dengan mode Gelap/Terang.

**Lokasi**: `/var/www/apppatrol-admin`
**Framework**: Next.js 16 (React) - TailAdmin Template

**Modul Tersedia:**
1.  **Dashboard**: Statistik presensi realtime.
2.  **Monitoring Presensi**: Tabel log absen harian dengan filter tanggal & departemen.
3.  **Master Karyawan**: Tabel manajemen data karyawan super lengkap (28+ kolom) dengan fitur scroll horizontal dan aksi cepat (WA, Edit, Lock).

---

## 6. Integrasi & Alur Data

### Contoh Kasus: Menambah Karyawan Baru
1.  (Saat ini) Admin menambah data via **Laravel Web** (Legacy).
2.  Data masuk ke tabel `karyawan` di database MySQL `patrol`.
3.  Foto disimpan di folder `storage` Laravel.
4.  API Python (`/api/master/karyawan`) membaca data baru tersebut dari database.
5.  Frontend Next.js menerima JSON dan menampilkannya di tabel **Master Karyawan** baru, lengkap dengan foto yang diambil dari mounted storage.

### Contoh Kasus: Presensi Harian
1.  Karyawan absen via **Mobile App**.
2.  Data masuk ke tabel `presensi`.
3.  Dashboard Next.js (`/presensi`) meminta data terbaru ke Python API.
4.  Python API query ke tabel `presensi` dan mengembalikan data real-time ke Admin.

---

## 7. Cara Menjalankan Full System

### 1. Database & Laravel (Existing)
Pastikan service MySQL dan Web Server (Apache/Nginx) untuk Laravel sudah berjalan normal.

### 2. Backend Python (API Service)
```bash
cd /var/www/appPatrol-python
source .venv/bin/activate
python3 app/main.py
```
*   Server: `http://localhost:8000`

### 3. Frontend Next.js (Admin UI)
```bash
cd /var/www/apppatrol-admin
export PORT=3001
npm run dev
```
*   Akses: `http://localhost:3001`
