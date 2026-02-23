# Rancangan Optimasi Enterprise Sistem Keamanan & Absensi (K3Guard)

Dokumen ini memuat cetak biru (*Blueprint*) progres dan daftar tugas (*Task List*) untuk meningkatkan arsitektur keamanan, absensi, dan mitigasi pelanggaran aplikasi K3Guard dari level fungsional dasar menjadi sebuah sistem **Enterprise Security Management**. 

---

## 🔥 Fase 1: Proactive Fraud Reporting & Escalation
*Fokus:* Merubah sistem pelaporan pelanggaran (Fake GPS, Wajah Gagal, Root Device) dari sistem pemantauan pasif "Tunggu Dilihat di Dasbor" menjadi Eskalasi Otomatis (Notifikasi Push ke Atasan secara Real-Time).

### Step 1.1: Eskalasi Alarm Liveness / Face Verification Gagal (On Progress)
- \[x\] **Modul Endpoint:** `/api/android/security/report-abuse` (di `emergency_legacy.py`).
- \[x\] **Alur Modifikasi:** Saat satpam gagal memindai wajah `> 5x` limit (sistem mengirim `blocked: true`), sisipkan fungsi broadcast **Push Notification FCM (Firebase)**.
- \[x\] **Target Notifikasi:** Admin / NIK Atasan, atau "Seluruh Akun dengan Role Admin/Danru" pada cabang yang bersangkutan.
- \[x\] **Pesan Tersalur:** `"🚨 PERINGATAN! Perangkat NIK: [xxx] terkunci akibat manipulasi/kegagalan pemindaian wajah berturut-turut!"`

### Step 1.2: Eskalasi Real-Time Alarm Mock Location (Fake GPS) (To-Do)
- \[x\] **Target Monitoring:** Saat Android mengirim koordinat lokasi secara berkala (yang menandakan aplikasi Fake GPS terdeteksi), Android biasanya mengirim `isMockLocation = true`.
- \[x\] **Alur Modifikasi:** Saat API menerima flag siluman ini (biasanya di API Employee Tracking/Lokasi), tidak hanya mencatatkan bendera "merah" di Database, sistem harus bereaksi cepat membunyikan klakson *(Push Notification)* ke dasbor Web atau ponsel Atasan pos tersebut secara _Real-Time_.

### Step 1.3: Eskalasi Alarm Deteksi "Force Stop" Aplikasi (Selesai)
- [x] **Target:** Aplikasi diclose secara sengaja dari "Recent Apps" (Swipe To Kill) tanpa melalui proses logout.
- [x] **Tindakan:** Mengirim API secara asinkron saat aplikasi dihidupkan ulang dan memberi sinyal bahaya ke dasbor Atasan via Push Notif.

### Step 1.4: Integrasi UI Daftar Pelanggaran Terpusat (Beranda & Halaman Notifikasi) (Selesai)
- [x] **Target Visual:** Menampilkan log seluruh bentuk pelanggaran keamanan (Fake GPS, Force Close, Face Verify Gagal) ke dalam antarmuka Web Admin/Dasbor Atasan.
- [x] **UI Beranda (Dashboard):** Membuat sistem penayangan **Modal Peringatan** di halaman beranda saat terjadi pelanggaran, serta menyediakan sebuah **Icon Notifikasi** interaktif yang mengarahkan pengguna ke halaman khusus notifikasi.
- [x] **Halaman Notifikasi (List View):** Menyajikan data pelanggaran dalam bentuk *List* terperinci di dalam halaman khusus notifikasi. Jika notifikasi historis sudah tidak relevan/tidak ada pelanggaran, tampilannya akan disesuaikan (atau dikosongkan/dihapus).
- [x] **Tujuan:** Agar siklus penanganan mitigasi keamanan terkunci sempurna (Closed-Loop) di mana atasan tidak hanya menerima sinyal FCM di HP, namun terarah mengelola daftar pelanggarannya melalui list yang konsisten di dalam aplikasi/website.

---

## 🛡️ Fase 2: Flexibilitas Keamanan Regional (Geofence & Unlock)
*Fokus:* Mengurangi keluhan satpam di pos/area yang sinyal GSM/GPS-nya terhalang bukit/gedung (sering memicu False Positive *"Di Luar Radius"* padahal sudah di Pos), tanpa mengorbankan integritas sistem.

### Step 2.1: Fitur Pembebasan Radius Sementara *"Luar Pagar"* (Selesai - Backend API done)
- [x] **Target Fitur:** Memungkinkan Satpam meminta pembebasan (bypass) `lock_location` kepada atasan jika koordinat HP-nya meleset dari lokasi cabang karena akurasi GPS buruk.
- [x] **Flow Android (API):** `/api/android/absensi/request-bypass-radius` siap menerima *"Ajukan Izin Absen Luar Tapak"*.
- [x] **Flow Backend/Admin:** Web Dasbor Admin menerima *Alert Izin* via API `/security/notifications/security-alerts`, dan admin memanggil `/security/notifications/approve-bypass` -> Mengubah status `lock_location = 0` (Hanya untuk 1 hari/1 Sesi Absen).

---

## 📊 Fase 3: Pencatatan Log Security (Audit Trail & Turlalin)
*Fokus:* Menjamin bahwa seluruh transaksi keluar/masuk satpam dan kendaraan tidak dapat diotak-atik/diedit oleh satpam itu sendiri setelah tersimpan.

### Step 3.1: Sinkronisasi Identitas Pencatat (Selesai)
- [x] **Modul:** Turlalin (Pengatur Lalu Lintas Kendaraan) & Tamu (Modul Legacy).
- [x] **Masalah Saat Ini:** Kadang Log Turlalin/Tamu kurang mengikat informasi *ID Anggota yang mencatat masuk vs Anggota yang mencatat keluar*. 
- [x] **Solusi:** Sistem Enterprise mewajibkan *Stamp* waktu absolut dari Server (`datetime.now()`) yang dikombinasikan dengan NIK dari token, agar Anggota di lapangan tidak leluasa "Memalsukan Jam Masuk Kendaraan" menggunakan jam lokal ponsel mereka.

---

## 🚦 Status Eksekusi Saat Ini (Current Progress)
- [x] Sentralisasi Key & Server WS URL ke `pengaturan_umum` Database **(SELESAI)**
- [x] Pemetaan Skema Aplikasi Android (Alur Face Verify & Radius Check) **(SELESAI)**
- [x] Integrasi FCM Alarm Eskalasi (Wajah / Abuse Block) di `emergency_legacy.py` **[Selesai! ��]**

*Catatan: File ini `/var/www/appPatrol-python/docs/enterprise_optimizations_plan.md` bertindak sebagai kompas pelacak status untuk setiap baris perintah modifikasi yang kita lepaskan ke Server Peladen (API).*
- [x] Integrasi FCM Real-Time Notif Fake GPS di `tracking_legacy.py` **[Selesai! 🚀]**

### Step 1.3: Deteksi Pemutusan Aplikasi Paksa (Force Close) & Restarts
- [x] **Modul Endpoint:** `/api/android/security/report-abuse` (Python) & `MainActivity.kt` (Android).
- [x] **Alur Modifikasi:** Android memantau kondisi *lifecycle*. Jika aplikasi dijalankan tapi sebelumnya tertutup tidak wajar (bukan `onDestroy` / ditutup paksa / Force Stop oleh Satpam untuk mencurangi waktu/lokasi), saat re-open, Android akan langsung mengirim `type=APP_FORCE_CLOSE` ke backend.
- [x] **Aksi Backend:** Menerima laporan. Bila dalam jam dinas/shift aktif aplikasi dimatikan paksa, lapor Danru via FCM, dan berikan balasan Modal 'Peringatan Penutupan Paksa' di layar Satpam. **[Selesai! 🚀]**
- [x] **Optimasi Dasbor:** Peringatan "Aplikasi Ditutup Paksa" dihapus dari *Popup Modal* layar penuh di Dasbor Web agar tidak mengganggu navigasi navigasi (Spamming), dan dipindahkan eksklusif ke dalam Ikon Notifikasi Header **[Selesai! 🚀]**

---

## 🛠️ Fase 4: Stabilitas Sesi & Pengalaman Pengguna (UX Bug Fixes)
*Fokus:* Merapikan celah kritis pada alur login (terlempar tiba-tiba) dan repetisi persetujuan dokumen pengguna (EULA/Privacy) yang mengganggu kenyamanan.

### Step 4.1: Sinkronisasi Zona Waktu Sesi (Timezone Token Issue) (Selesai)
- [x] **Masalah:** Semua Karyawan terus terlempar keluar dari Android dengan pesan "Sesi berakhir karena login di perangkat lain". Hal ini memicu Force Logout berangkai.
- [x] **Akar Penyebab (Root Cause):** Backend membandingkan waktu terbitnya token (menggunakan zona waktu UTC lokal `utcfromtimestamp`) dengan waktu tabel pengguna di Database (yang sudah terkonversi ke Waktu Jakarta/Lokal). Akibatnya, Token selalu dianggap "Lebih usang/kadaluarsa" dari `updated_at`.
- [x] **Solusi Presisi:** Semua modul keamanan Android (`auth_legacy.py`, `permissions.py`) telah diseragamkan dengan membaca `fromtimestamp` agar waktu token setara dengan jam lokal Indonesia.

### Step 4.2: Pencegahan Repetisi User Agreements & Privacy Policy (Selesai)
- [x] **Masalah:** Aplikasi Android memunculkan terus Layar Syarat & Ketentuan setiap kali pengguna habis *Logout*/Login ulang, dan membuahkan ribuan duplikat baris persetujuan di Database (`user_agreements`).
- [x] **Akar Penyebab (Root Cause):** Aplikasi Android membersihkan tembolok lokal (DataStore) setiap *logout*, dan saat login menganggap belum ada persetujuan yang ditandatangani. Di lain pihak, Backend asal mencatatkan data baru setiap dikirimkan persetujuan.
- [x] **Solusi Bypass Backend:** Endpoint Cek Versi Aktif Android (`/api/android/terms/active` & `/api/android/privacy/active`) kini memeriksa secara diam-diam (*silent check*) ke dalam Database. Jika user sudah pernah menyetujui versi aktif, Backend membalas dengan versi kosong (`""`). Hasilnya, Android mengabaikan kemunculan *Modal* tersebut. Di saat yang bersamaan, perlindungan lapisan ganda di endpoint penyimpanan (`/api/android/compliance/agreement`) kini akan memblokir (*early return*) percobaan injeksi data bila divalidasi sebagai duplikat.

### Step 4.3: Perbaikan Sinkronisasi Histori Jadwal Patroli (Selesai)
- [x] **Masalah:** Pada riwayat jadwal patroli, status jadwal yang belum dikerjakan (pending) malah tercentang selesai (done) oleh nama karyawan lain yang mengerjakannya di masa depan/lampau, yang mengunci jadwal saat ini bagi shift berjalan.
- [x] **Akar Penyebab (Root Cause):** Backend versi lama memvalidasi status grup menggunakan patokan waktu sistem di dalam database yang rentan bias timezone server (`created_at <= batas_akhir_jadwal`), alih-alih merujuk pada `tanggal` kalender yang dipasangkan dengan input `jam_patrol`.
- [x] **Solusi Presisi:** Modul `/getPatrolHistory` dirombak untuk mengabaikan fungsi filter *query* rentang `created_at`. Evaluasi silang jadwal (termasuk deteksi tugas *cross-midnight* / lintas hari) kini dihitung di taraf memori menggunakan kombinasi natural objek tanggal kalender dan waktu (*Date Time Combine*) yang diisi oleh karyawan sesungguhnya saat absen, menciptakan representasi baris (*payload*) yang linier bagi antarmuka Android.
