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
