# Rencana Migrasi API Android: Laravel ke Python FastAPI ("Jalur Postman")

Dokumen ini merinci strategi teknis untuk memindahkan jalur komunikasi aplikasi Android **GuardSystemApp** dari backend legacy (Laravel) ke backend modern (Python FastAPI) secara bertahap dan aman.

## 1. Latar Belakang & Tujuan
*   **Kondisi Saat Ini**: Aplikasi Android (`GuardSystemApp`) di Play Store berkomunikasi 100% dengan backend Laravel (`/var/www/appPatrol`).
*   **Tujuan**: Mengarahkan versi aplikasi Android **yang akan datang (v2.0+)** untuk berkomunikasi langsung dengan backend Python (`/var/www/appPatrol-python`).
*   **Manfaat**: Performa lebih tinggi (FastAPI Async), kemudahan pengembangan fitur AI/Real-time, dan modernisasi stack teknologi.

---

## 2. Strategi Migrasi Bertahap (Zero Downtime)

Kita tidak akan mematikan Laravel seketika. Kedua backend akan berjalan berdampingan ("Dual Stack").

### Fase 1: Persiapan Backend Python (Shadowing)
Pada tahap ini, kita menyiapkan endpoint di Python yang **identik** secara struktur request/response dengan endpoint Laravel yang ada.

*   **Tugas Backend Python**:
    *   Membuat endpoint `POST /api/login` yang menerima `username`, `password`, `device_model`.
    *   Membuat endpoint `POST /api/absensi` yang menerima foto & lokasi.
    *   Memastikan format JSON response **sama persis** dengan Laravel (agar Android tidak crash).
    *   **Autentikasi**: Python harus bisa menerbitkan Token Akses (bisa JWT atau mirip Sanctum) yang valid.

### Fase 2: Rilis Aplikasi Android v2.0 (Trial)
Pada tahap ini, kita merilis update aplikasi Android ke **Internal Test Track** atau **Beta** di Play Store.

*   **Tugas Android (Kotlin)**:
    *   Mengubah `BASE_URL` di `RetrofitClient.kt`:
        *   **Lama**: `https://k3guard.com/api/` (Laravel)
        *   **Baru**: `https://api-v2.k3guard.com/` (Ke Server Python)
    *   Melakukan testing fitur krusial: Login, Absensi, Patroli.
*   **Hasil**: User dengan aplikasi versi baru (v2.0) akan masuk ke "Jalur Python". User lama (v1.x) tetap di "Jalur Laravel". Database yang digunakan tetap **SAMA** (MySQL Shared).

### Fase 3: Pemindahan Fitur Kompleks (Partial Migration)
Jika memindahkan `Login` terlalu berisiko di awal, kita bisa memindahkan fitur per fitur:

*   **Skenario Hibrid**:
    *   Android v2.0 tetap Login ke Laravel (`https://k3guard.com/api/login`) untuk dapat Token.
    *   Untuk fitur berat seperti **Patroli** atau **Upload Laporan**, Android v2.0 memanggil endpoint Python (`https://api-v2.k3guard.com/patroli/...`).
    *   **Syarat**: Python harus bisa memvalidasi Token yang dibuat oleh Laravel (Integrasi Token Database).

### Fase 4: Full Switch & Deprecation
Setelah versi Android baru stabil dan mayoritas user sudah update:

*   Matikan endpoint Laravel yang sudah tidak dipakai (atau redirect ke Python).
*   Jadikan Python sebagai backend utama sepenuhnya.

---

## 3. Langkah Teknis Implementasi

### A. Setup Infrastruktur (DevOps)
1.  Siapkan subdomain atau route baru di Nginx, misal `api-v2.k3guard.com` atau `k3guard.com/api-python/`.
2.  Arahkan route tersebut ke **Port 8000** (Python FastAPI).
3.  Pastikan SSL/HTTPS aktif (agar Android mau connect).

### B. Development Backend Python
1.  **Replikasi API Login**:
    *   Buat `router/auth.py`.
    *   Cek password hash (Bcrypt) di tabel `users`.
    *   Generate Token.
2.  **Replikasi API Utama**:
    *   `router/attendance.py` (Absensi).
    *   `router/patrol.py` (Patroli).
3.  **Testing**: Gunakan **Postman** untuk membandingkan output JSON Laravel vs Python. Harus identik.

### C. Development Android
1.  Buat *Flavor* baru (misal `dev` atau `staging`) di Android Studio.
2.  Ubah `RetrofitClient` agar Base URL bisa dikonfigurasi dinamis atau hardcode ke URL Python baru.
3.  Build APK -> Test -> Release.

---

## 4. Keuntungan & Risiko

| | Laravel (Legacy) | Python FastAPI (New) |
| :--- | :--- | :--- |
| **Kinerja** | Synchronous (Blocking) | Async (Non-blocking, Cepat) |
| **Fitur AI** | Terbatas / Lambat | Native (Face Rec., Data Science) |
| **Risiko** | Stabil (Sudah jalan) | Perlu testing ketat (Regresi) |

**Kesimpulan**: Rencana ini ("Jalur Postman") sangat layak (feasible). Dengan database yang sama, risiko data tidak sinkron sangat minim. Kuncinya adalah menjaga kompatibilitas format JSON API.
