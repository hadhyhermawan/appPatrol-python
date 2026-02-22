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

### D. Simulasi Pengingat Absen Patroli (Push Awal + Mode Ping Audio Berulang)
Sistem Patroli K3Guard memiliki tingkat ketegasan (**Snooze Agresif**) khusus. Syarat mutlaknya: Karyawan wajib sudah melakukan "Absen Masuk" kerja dulu di hari itu! Selanjutnya, Notifikasi _Pop-Up text_ hanya dikirim **satu kali** di awal, disusul teror _Ping Audio_ setiap 5 menit gaib di latar belakang agar layar HP tidak kepenuhan spam.

**Anggaplah Data Pak Budi (NIK: `1801042008930002`):**
- Shift : `SF PAGI (08:00:00 - 16:00:00)`.
- Jadwal Patroli di *Dashboard* ada 4: 
  - Patrol 1 (`08:00 - 10:00`)
  - Patrol 2 (`10:00 - 12:00`)
  - Patrol 3 (`12:00 - 14:00`)
  - Patrol 4 (`14:00 - 16:00`)

Inilah urutan eksekusi alarm di lapangan:

1. **Kasus Patrol 1 (`08:00 - 10:00`) - Gagal Ping Karena Belum Absen Masuk:**
   - **Pukul 07:55**: Server bersiap melempar peringatan *"Waktunya Patrol 1!"*. Namun saat dicek ke tabel Presensi, `jam_in` Pak Budi ternyata masih KOSONG (Dia belum datang ngantor).
   - **Hasil**: Server **menggugurkan peringatan**. HP Pak Budi diam 100%. Bahkan selama rentang 08:00, 08:05, hingga 10:00 tidak ada _Ping Audio_ sama sekali karena sistem menganggapnya belum hadir (Tidak boleh menagih pekerjaan ke orang yang tidak ada).
   - *Catatan: Jika rentang ini telanjat habis (10:01) dan belum dikerjakan, Patrol 1 otomatis gugur dan dianggap "Missed" / Tidak Dikerjakan.*

2. **Kasus Patrol 2 (`10:00 - 12:00`) - Fungsi Normal & Audio Berulang:**
   - **Pukul 08:30**: Pak Budi akhirnya sampai di Pos dan mengetuk "Check-In" (*Absen Masuk Pagi*).
   - **Pukul 09:55**: Menjelang jadwal Patrol 2, server mengecek lagi. Karena status masuk kerjanya sekarang sudah _Valid_, Server menembakkan Pelatuk Penuh: Layar HP menyala dengan Notifikasi Visual: *"Waktunya memulai Patrol 2!"* disertai memutar Vokal MP3 Peringatan Patroli.
   - **Pukul 10:00, 10:05, 10:10... dst:** Memasuki periode aktif, Pak Budi rupanya sedang ngopi. Daripada menimbun banner di Layar HP, Server mengirim balok gaib ber-_flag_ `audio_only: true`. HP Pak Budi di saku secara ajaib berteriak menggaungkan vokal Peringatan MP3 setiap kelipatan 5 Menit tanpa henti!
   - **Resolusi (Penyelesaian):** Di pukul `10:12` karena risih dibully HP-nya, Pak Budi membuka aplikasi lalu menjalankan Patroli (Scan NFC ke-1). Pada pukul `10:15` dan seterusnya, rentang tugas di jam ini dianggap sudah *Active/Done*, pelatuk alarm otomatis mati serentak. Pak Budi tenang kembali.

3. **Kasus Patrol 3 & 4 - Berlaku Sama Seterusnya:**
   - Karena di tahap sebelumnya Pak Budi sudah terdeteksi Sah hadir kerja dari Pagi, saat jam menunjuk pukul `11:55` (Pra-Patrol 3), ia akan mendapat 1 Push Notifikasi Teks. Jika abai lagi, siklus _Ping_ gaib audio per-5 menitnya akan menyerang kembali di rentang `12:00-14:00`, begitupun untuk siklus tahap akhir di Patrol 4 Pra-Kepulangan. Penderitaan audio akan terus memburuku selama titik-titik tersebut tidak diselesaikan/di-scan aplikasinya.

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
