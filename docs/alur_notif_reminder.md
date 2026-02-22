# Dokumentasi Alur Notifikasi & Pengingat (Reminder)

Dokumen ini menjelaskan arsitektur jalannya Sistem Firebase Cloud Messaging (FCM) dan _Cron Job_ (APScheduler) untuk mendistribusikan notifikasi maupun suara pengingat kerja (_Reminder_) ke Aplikasi Android (K3Guard).

## 1. Arsitektur Pengingat Otomatis (_Reminder Scheduler_)
Sistem backend (Python FastAPI) memiliki sebuah fungsi (_task_) bernama `run_reminder_check()` pada `/app/services/reminder_scheduler.py` yang dieksekusi **Setiap 1 Menit** secara berulang sejak Server pertama dijalankan.

### A. Alur Kerja _Backend_ (Server)
1. **Deteksi Aturan**: Server membaca konfigurasi peringatan dari tabel `reminder_settings` di Database. Tabel ini menyimpan target penerima (Level Jabatan/Role, Cabang, Departemen), toleransi menit, dan pesannya.
2. **Sinkronisasi Algoritma Jadwal (Hierarki Presisi)**: Server mengenali *shift* jadwal masing-masing personal melalui fungsi tunggal `determine_jam_kerja_hari_ini`. Ini adalah hierarki mutlak yang sama 100% yang di-desain untuk Absensi (*Ekstra* ➔ *Tanggal* ➔ *Hari/Roster* ➔ *Departemen* ➔ *Umum*). 
3. **Penyaringan Karyawan Absen & Libur**: 
   - Server membandingkan target di atas dengan log tabel transaksi absensi yang dikembalikan fungsi penentu di atas. 
   - Jika saat ini HP Karyawan terasosiasi dengan kode `"LIBR"` atau kalimat *"Libur"*, dia tidak akan di-ping.
   - **Jika karyawan sudah terdeteksi melaksanakan ketukan** sebelum menit pengingat tersebut (*`jam_in is not None`* untuk Pagi / *`jam_out is not None`* untuk Sore), nama karyawan itu secara otomatis **dicoret** dari daftar, untuk mencegah *spam* yang memekakkan kuping.
4. **Push ke FCM**: Sisa NIK yang lolos penyaringan akan dikumpulkan `fcm_token`-nya. Lalu Server Firebase menembakkan notifikasi asinkronus ke HP Karyawan dengan JSON Payload tipe `"reminder"` dan *subtype* (Misal: `absen_masuk`, `absen_pulang`, atau `absen_patroli`).

### B. Alur Kerja _Android_ (Penerima)
1. Perangkat akan menerima gedoran FCM melalui *Service* yang tetap siaga di latar belakang (*`/app/src/main/java/com/k3guard/system/firebase/FirebaseMessagingService.kt`*).
2. FirebaseMessagingService kemudian akan meloloskan data masuk ke dalam gerbang blok kondisi: _Apakah payload ini betipe "reminder"?_ Jika valid, *Service* menyuntik baris UI notifikasi _Push_ yang muncul di layar (Channel: `Pengingat Kerja`).
3. **Pemisahan Sumber Audio**: 
    - Supaya suara OS bawaan tidak menindih _Media Player_ kustom milik aplikasi, **OS Notification Channel diset *"SUST"/BISU* 100% (`setSound(null)` pada pembuatan Android _Channel ID `reminder_channel_v2`_)**.
    - Aplikasi lalu membangkitkan layanan `MediaPlayer` tersendiri secara paralel yang memutar instruksi Vokal MP3 spesifik (`R.raw.absen_masuk` vs `R.raw.absen_pulang`) milik folder OS ke Speaker HP.

### C. Simulasi Pengingat Absen Pulang (Shift Selesai) di Lapangan
Admin K3Guard membuat peringatan otomatis: *"Ingatkan karyawan untuk **Absen Pulang** tepat 15 menit sebelum jam shift berkahir."*
**Jadwal Pak Budi:** Shift Pagi, Jam Pulang 16:00 WIB.
- **Pukul 15:45:** Server menyisir seluruh personil yang jadwal pulangnya pukul 16.00 WIB. Server kemudian memeriksa log tabel absensinya hari ini.
- **Validasi Server:** *"Pak Budi tadi pagi sudah Check-In (jam_in ada isinya), TAPI kolom Check-Out (jam_out)-nya masih KOSONG"*. Karena statusnya masih *"Menggantung"* (Sedang Bekerja) di Pos, Server berhak memanggilnya.
- **Hasil:** Layar HP Pak Budi menyala dan berteriak *"Masuk Waktu Absen Pulang...!"*, mengingatkannya untuk tidak lupa ketuk Check-Out di aplikasi sebelum ia melepas seragam dan pulang ke rumah.
- *Pengecualian:* Jika sebelum jam 15:45 Pak Budi membolos pulang lebih awal (sudah klik *Check-out*), Server **TIDAK AKAN** membunyikan HP-nya lagi, karena transaksinya dinyatakan sudah selesai (*Closed*).

### D. Simulasi Pengingat Absen Patroli (Shift Titik)
Sama dengan presensi harian, patroli kini difilter secara cerdas bukan berdasarkan asal tebak anggota departemen, melainkan dengan memeriksa **Kesesuaian Shift Karyawan** dengan **Batas Waktu Patroli (Time Window)**.
- **Pukul 22:45**: Jadwal Patroli Gedung B dijadwalkan pada `23:00 - 00:00`.
- **Validasi Server**: Server mendata *seluruh* Satpam di Shift Malam hari itu. Lalu memindai tabel `patrol_sessions` untuk meneliti apakah di antara rentang waktu tersebut *sudah ada* Satpam yang berkeliling atau menekan *Mulai Patroli*.
- **Hasil**: Apabila belum ada satupun yang berkeliling, alarm "Waktunya Patroli..." akan menyala di semua HP Satpam Shift Malam tersebut. Namun jika satu orang saja dari rekan satu timnya sudah mulai absen keliling, Server membatalkan notifikasi (karena tugasnya sudah diwakilkan/diselesaikan).

---

## 2. Alur Notifikasi Bypass & Chat
Sistem juga memiliki distribusi "Notifikasi Sekali Jalan" (_Event-Driven_), seperti halnya permohonan Radius Izin Bypass, Chat Obrolan, Darurat, serta Berita. 

### A. Izin Absen di Luar Jangkauan (Radius Bypass)
- **Sumber Pemicu**: Dipanggil saat Karyawan memencet "Req. Bypass Radius" / Mematikan Deteksi GPS Paksa dari tombol Android Dashboard. Alur ini berada di file backend `/api/android/absensi/request-bypass-radius`.
- **Arah Serangan**: Bukannya meneruskan persetujuan secara instan, DB justru menggantung _Request_-nya sebagai Status _"Pending"_ di tabel Laporan Keamanan (*`security_reports`*). Backend kemudian **memeriksa seluruh relasi** (Rekan atau Pimpinan) satu-Cabang dari si peminta.
- **Multicasting**: API mengebut penembakan *Push Notifications* FCM *(Target < 500 Token)* ke arah seluruh rekan satu pos dengan judul *"Izin Absen Luar Tapak"*.

### B. Distribusi Sinyal Notifikasi Latar Belakang (General / General Fallback)
Di aplikasi lama, blok _Payload_ Chat yang datang menyambar tak terkategori akan menyerap sinyal *"Izin Bypass"* ini dan UI menjadi bertuliskan *"Pesan Baru"*. 

**Perbaikan Flow (Mulai 22 Februari 2026)**
- Semua logika di `FirebaseMessagingService` telah dirantai ulang *(Strict-Checking Firebase Parsing System)*.
- Jika _Server_ memompa payload bertipe `"chat"`: Aplikasi secara eksklusif membunyikan peringatan *"Pesan Obrolan Baru"*, lalu menembakkan sinyal siaran (*LocalBroadcastManager `CHAT_NEW_MESSAGE`*) supaya *RecyclerView_UI* memanggil API secara gaib dan layar pengguna diperbarui isian chat barunya tanpa di-_Reload_.
- Jika semua pengecekan (`"chat"`, `"video_call"`, `"reminder"`, `"news"`, `"emergency"`) terlewati, Aplikasi memiliki **Jaring Pendaratan Akhir (_General Notification Fallthrough_)** (*General Notification*) yang akan membangun blok teks notifikasi standar memakai variabel bawaan `title` dan `body` murni bawaan dari instruksi API Cloud. Hal ini menghalau munculnya Label *"Pesan Baru"* yang tak wajar.

`(Dokumentasi dihasilkan dan diperbarui otomatis oleh Asisten Antigravity pada 22/02/2026)`
