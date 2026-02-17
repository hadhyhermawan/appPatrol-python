# 🗺️ Master Plan: Migrasi Laravel ke FastAPI + Next.js

## 📚 Pendahuluan
Dokumen ini berfungsi sebagai **blue print** migrasi sistem backend dari Laravel (PHP) ke **Python (FastAPI)**, serta penggantian frontend admin menjadi **Next.js**.

**Tujuan Utama:**
1.  Meningkatkan performa API (terutama untuk traffic tinggi).
2.  Integrasi *native* dengan modul AI (Face Recognition) yang sudah berbasis Python.
3.  Modernisasi tampilan Admin Dashboard.
4.  **CRITICAL:** Menjaga kompatibilitas 100% dengan aplikasi Android yang sudah live di Playstore.

---

## 🏗️ Arsitektur Sistem Baru

| Komponen | Lama (Legacy) | Baru (Target) | Keterangan |
| :--- | :--- | :--- | :--- |
| **Backend API** | Laravel 9+ (PHP) | **FastAPI (Python)** | High Performance, Async support |
| **Admin Panel** | Blade Template | **Next.js (React)** | SPA, Modern UI, Interaktif |
| **Database** | MySQL / MariaDB | MySQL / MariaDB | **Tetap Sama** (Shared DB during migration) |
| **Auth** | Laravel Sanctum | **JWT (JSON Web Token)** | User harus login ulang 1x saat switch |
| **AI Engine** | HTTP Calls ke Flask | **Direct Import** | Tidak ada overhead HTTP request internal |
| **Realtime** | Pusher / Polling | **WebSocket (Native)** | Lebih cepat untuk Tracking & Chat |

---

## 🗓️ Fase Pengerjaan (Step-by-Step)

### Fase 1: Setup Lingkungan (Foundation) ✅ KOMPLIT
**Target:** Menyiapkan project FastAPI yang bisa terkoneksi ke database lama.

1.  **Inisialisasi Project FastAPI** (✅ Selesai)
    -   Setup folder `/var/www/appPatrol-python`.
    -   Setup Virtual Environment (`venv`).
    -   Install dependencies: `fastapi`, `uvicorn`, `sqlalchemy`, `mysql-connector-python`, `pydantic`, `python-jose` (untuk JWT).
2.  **Koneksi Database (Existing)** (✅ Selesai)
    -   Konfigurasi koneksi ke database `patrol` yang sedang dipakai Laravel.
    -   **PENTING:** Jangan lakukan migrasi (create table) baru. Gunakan table yang sudah ada.
3.  **Reverse Engineering Model** (✅ Selesai)
    -   Gunakan tools seperti `sqlacodegen` untuk generate model Python (SQLAlchemy) otomatis dari database MySQL yang sudah ada.
    -   Hasil: Model User, Absensi, Patroli, dll di Python sudah siap pakai.

### Fase 2: Implementasi Auth & Core API (Android Mirroring) ✅ KOMPLIT
**Target:** API Python bisa melayani login dan membuat token yang valid.

1.  **Auth (JWT)** (✅ Selesai)
    -   Buat endpoint `POST /api/login`.
    -   Validasi hash password (Laravel pakai `bcrypt`, Python `bcrypt` mendukung ini).
    -   **Response:** JSON sama persis dengan output Laravel (Token, User Object).
    -   **Token:** Menggunakan JWT (JSON Web Token) yang stateless.

### Fase 3: Pengembangan Admin Dashboard (Next.js) ✅ KOMPLIT (Initial)
**Target:** Admin bisa login dan melihat dashboard via web baru.

1.  **Setup Project Next.js** (✅ Selesai)
    -   Setup Next.js + Tailwind di `/var/www/apppatrol-admin`.
    -   Halaman Login yang terhubung ke FastAPI.
    -   Halaman Dashboard dengan statistik realtime (Patroli, Absen).
    -   Proxy Nginx: `https://frontend.k3guard.com` -> Next.js (3001) -> Python API.

### Fase 4: Fitur Utama (Absensi & Patroli) 🚧 NEXT
**Target:** Migrasi logika bisnis inti.

1.  **Integrasi Face Recognition**
    -   Porting logika dari folder `/var/www/appPatrol/deteksiwajah-api` langsung ke dalam FastAPI.
2.  **Endpoint Absensi & Patroli**
    -   Migrasi `PatroliApiController.php` -> `routers/patroli.py`.
    -   Pastikan URL sama persis: `/api/patroli/absen`, `/api/patroli/check-absen`.

### Fase 5: Testing & "Switch Over" (Go Live)
**Target:** Memindahkan traffic dari Laravel ke FastAPI tanpa downtime lama.

1.  **Shadow Run (Parallel Run)**
    -   Jalankan FastAPI di port beda (misal: 8000).
    -   Arahkan **Aplikasi Android DEBUG** ke port 8000.
    -   Lakukan Full Test: Login, Absen Wajah, Patroli, Kirim Laporan.
2.  **Switch Over**
    -   Ubah config Nginx utama untuk mengarah ke FastAPI.

---

## 📂 Struktur Folder Baru

```text
/var/www/
├── appPatrol/              <-- (Laravel Lama - Backup/Reference)
├── appPatrol-python/       <-- (Backend Baru - FastAPI)
│   ├── app/
│   │   ├── core/           <-- Config, Security, Database
│   │   ├── models/         <-- SQLAlchemy Models (Hasil Generate)
│   │   ├── schemas/        <-- Pydantic Models (Validasi Request/Response)
│   │   ├── routers/        <-- Endpoints (Auth, Patroli, Absensi)
│   │   ├── services/       <-- Logic Bisnis (Face Recog, Kalkulasi)
│   │   └── main.py         <-- Entry Point
│   ├── .env
│   ├── requirements.txt
│   └── alembic.ini         <-- Migrasi DB (jika ada perubahan nanti)
│
└── apppatrol-admin/        <-- (Frontend Baru - Next.js)
    ├── src/
    │   ├── app/            <-- Pages & Routing
    │   ├── components/     <-- UI Components
    │   ├── lib/            <-- API Client
    │   └── ...
    ├── package.json
    └── next.config.js
```
