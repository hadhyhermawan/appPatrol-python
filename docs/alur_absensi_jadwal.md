# Dokumentasi Logika Absensi (Presensi) & Penetapan Jam Kerja

Dokumen ini menjelaskan alur penentuan jadwal/jam kerja karyawan (Satpam/Karyawan) saat melakukan absensi (Check-In / Out) melalui API Android (`/api/android/absensi`). Ada beberapa lapisan (hierarki) prioritas dalam penentuan jam kerja dari mulai izin penempatan tanggal spesifik (terkuat) hingga ke nilai standar profilnya (terlemah). 

Penentuan ini sangat krusial, bila terjadi ketidaksesuaian/kesalahan _query_, pengguna di sistem lapangan (Aplikasi Android K3Guard) tidak bisa melakukan absensi atau jam masuk yang terekam akan keliru.

## 1. Tabel-tabel Database Relasional

Berikut daftar tabel MySQL dalam basis data terkait mesin penentuan Jadwal Kerja Absensi.

### `karyawan`
- Data induk (_Master_) Karyawan.
- Kunci `nik`, menyimpan penanda Cabang (`kode_cabang`), Departemen (`kode_dept`) maupun kode jadwal *default* harian si Karyawan (`kode_jadwal`).

### `presensi_jamkerja`
- Master rincian jam/shift yang tersedia di sistem perusahaan secara global.
- Menyimpan sandi shift (`kode_jam_kerja`), teks (`nama_jam_kerja` ex: 'SF MALAM'), Waktu awal operasional (`jam_masuk`), target kepulangan (`jam_pulang`) beserta label `lintashari` (= 1 jika shift tersebut melewati tengah malam, contoh 20:00 - 08:00 keesokan paginya).

### `presensi_jamkerja_bydate_extra` (Prioritas 0 / Paling Absolut)
- *Plotting/Setting* jadwal "Sangat Spesifik" per NIK dan Tanggal. Biasanya dipakai oleh fitur *Admin* untuk mengubah manual (*override*) Shift seseorang mendadak dalam satu hari (misl: harusnya masuk siang tapi diminta lembur pagi / menggantikan).
- Menyimpan `nik`, `tanggal`, `kode_jam_kerja`.

### `presensi_jamkerja_bydate` (Prioritas 1)
- *Plotting* Rutin kalender yang disusun untuk NIK tersebut berdasar tanggal. (Biasa digunakan Satpam untuk shift bulanan yang polanya bisa loncat-loncat).
- Menyimpan `nik`, `tanggal`, `kode_jam_kerja`.

### `presensi_jamkerja_byday` (Prioritas 2)
- Penentuan jadwal berdasarkan "Nama Hari" per NIK (Bukan Tanggal). Contohnya, setiap NIK A di hari "Senin - Jumat" wajib `0001` (Shift Pagi Umum).
- Menyimpan `nik`, `hari` (Senin, Selasa, dll), `kode_jam_kerja`.

### `presensi_jamkerja_bydept` & `presensi_jamkerja_bydept_detail` (Prioritas 3)
- Jadwal sapu jagat untuk seluruh anggota dalam 1 departemen di 1 cabang.
- Kalau Karyawan tidak ter-_plot_ hari/tanggalnya secara khusus, maka dia akan mengambil referensi hari (mis: "Senin") dari setelan generik milik Departemen (`kode_dept`) dan Cabangnya (`kode_cabang`).

### `presensi` (Tabel Transaksi Absen)
- Data *History/Log* rekam jejak setiap _Tap_ presensi di lapangan.
- Menyimpan `jam_in`, `jam_out`, beserta sandi `kode_jam_kerja` yang menempel untuk hari itu. 


---

## 2. Alur Pembacaan Jadwal Secara Sintetik & Hirarki
Pengecekan yang dilakukan sistem dilakukan saat Karyawan memencet tombol Check-In (Masuk) atau Cek Kehadiran Dashboard Hari Ini. Berikut tahapan yang dicek sistem untuk mencarikan jadwal (_function `determine_jam_kerja_hari_ini`_):

Sistem Python akan mencari `kode_jam_kerja` yang tepat dengan urutan **Fallback (*Gugur/Mencari ke bawah bila Kosong*)**:

1. **Sedang Berlangsung Kemarin Lintas Hari?**
   Jika Karyawan belum absen hari ini, sistem akan menengok 1 hari ke belakang. Apakah kemarin dia ditugaskan Shift Lintas Hari (`lintashari` = 1) namun `jam_out`-nya masih *NULL* (alias belum pulang / masih jaga)? Jika *Ya*, sistem akan *mengunci* jadwal jam_kerja karyawan pada hari ini tetap pada jadwal lintashari milik hari kemarin.

2. **Cek `presensi_jamkerja_bydate_extra` (Prioritas Inti)**
   Apakah manajer mendaftarkan *override shift* spesial untuk "NIK" dan "Tanggal Spesifik (Hari Ini)"? Jika Ya, gunakan itu.

3. **Cek `presensi_jamkerja_bydate`**
   Apakah ploting roster / *shift bulanan* untuk "Tanggal Hari ini" ada untuk NIK tersebut? Jika Ya, ikuti itu.

4. **Cek `presensi_jamkerja_byday`**
   Apakah ada setelan khusus untuk "Nama Hari (Mis: Senin)" bagi NIK tersebut?  Jika Ya, ikuti pola mingguan ini.

5. **Cek Group `presensi_jamkerja_bydept`** 
   Jika semua per-orangan kosong, pinjam rumus Departemen dan Cabangnya pada hari ini ("Senin"). 

6. **Kolom `kode_jadwal` Karyawan (Dasar)**
   Bila departemen pun tidak mengaturnya, lihat data Dasar / Profile Inti `karyawan.kode_jadwal` sebagai pertahanan terakhir. 

**Catatan Sinkronisasi UI Jadwal Bulanan Android:**
Mulai 22 Februari 2026, API endpoint pembaca Jadwal (*`/api/android/jamkerja/bulanan`*) khusus layar **Kalender Riwayat** di HP Karyawan juga telah mengadopsi 100% secara _apple-to-apple_ hierarki di atas. Hal ini menjamin bahwa shift harian maupun bulanan yang muncul di UI kalender Android tidak akan pernah meleset penanggalannya dari ketetapan _Server_.

---

## 3. Fitur Pencegah Bencana Shift Malam / _Early Tolerance_
Misal seorang satpam punya Shift **SF MALAM** (`00:00 - 08:00 Pagi`) pada **Tanggal B**. 
Kenyataan di lapangan, para Satpam sering bersiap diri dan melakukan pendaftaran absen masuk (*Check-in*) 5 hingga 10 menit lebih cepat di **Tanggal A** (Misal Pukul `23:55`).

Sistem standar akan kebingungan dan gagal (Karena di Tanggal A dia dianggap "Tidak punya jadwal Shift Malam!"). 

Oleh karena itu di `absensi_legacy.py` kita menggunakan injeksi **Shift Tolerence Look-ahead**.
- **Logika:** Jika waktu menekan Check-In adalah *Malem* (`>= 20:00:00`) dan si karyawan hari ini tidak mempunyai shift gantung, maka sistem akan **meneropong ke tanggal Esok Harinya** (Tanggal B).
- Bila di Tanggal B dia punya Shift yang masuknya jam `<= 06:00` Pagi (Contoh `00:00:00` itu masuk kategori ini), maka sistem akan menaruh Presensi absen tersebut otomatis sebagai kehadiran miliknya di Shift **Tanggal B**. Absensinya berhasil masuk mulus tanpa galat.

## 4. Proses Rekam Bukti (_Penyimpanan File_)
Semua tangkapan foto Wajah (`in/out`) dari Android/Kamera akan dikirim dan disimpan Backend Python dan dilempar isinya menuju direktori penyimpanan yang digandeng paralel dengan sistem Website Admin (_dulu Laravel, kini disatukan storage-nya_):
**Lokasi Direktori Fisik:** `/var/www/appPatrol/storage/app/public/uploads/absensi`
**Format Nama File:** `{NIK}-{TANGGAL_SEKARANG}-{in/out}.png`

Kemudian rincian jalannya (_Path_) ini disuntik ke tabel Transaksi `presensi` di kolom `foto_in` maupun `foto_out`.

## 5. Tata Kelola Data Perizinan (Sakit, Cuti, Izin, Dinas)
Karyawan yang berhalangan hadir memiliki alur data khusus yang diproses melalui _Approval_ (Persetujuan) oleh pimpinan di Website Admin. Sistem menanganinya dengan dua layer pencatatan:

1. **Tabel Pengajuan Spesifik**: Saat Karyawan mengajukan Izin/Cuti, sistem menampungnya di tabel formulir seperti `presensi_izinabsen`, `presensi_izincuti`, `presensi_izindinas`, atau `presensi_izinsakit`. Semua tabel ini memiliki kolom rentang _dari_ hingga _sampai_ serta kolom status persetujuan (`status` bernilai `1` jika **Disetujui**).
2. **Injeksi Langsung ke Tabel `presensi`**: Ketika Izin/Sakit telah resmi disetujui, rutinitas _Backend_ akan langsung memplot/_inject_ baris transaksi kehadiran Karyawan ke tabel utama `presensi` dengan cara memaksa kolom `status` menjadi abjad/flag perizinan:
   - `i` = Izin Absen
   - `s` = Sakit
   - `c` = Cuti
   - `d` = Dinas Luar

**Dampak pada API Android (`/api/android/absensi/hariini`)**:
- Komponen API akan membaca kode abjad tersebut dari tabel `presensi` milik hari itu dan mengembalikan indikator status `I` / `S` / `C` / `D` (Bukan sekadar `H` Hadir atau `A` Alpa) ke layar HP/Dashboard karyawan.
- Aplikasi Android dan API `absen` telah diprogram untuk memblokir secara paksa apabila ada Karyawan yang iseng menekan layar "Check-In" saat data mereka di server sudah dilabeli berhalangan hadir (*_Throw Error Alert: "Anda tidak dapat absen, status hari ini: IZIN/SAKIT"_*).  

## 6. Auto-Close (Fitur Lupa Absen Pulang)
Jika karyawan telah absen masuk dan bekerja namun **lupa untuk menekan tombol Absen Pulang** hingga melewati `(jam pulang + batas_jam_absen_pulang)`:
1. Sistem rutinitas *APScheduler* API Python (`auto_close_presensi.py`) akan mendeteksi baris tersebut sebagai kadaluwarsa.
2. Status presensi baris tersebut akan dikunci mati dan ditimpa paksa menjadi `status = 'ta'` (Tidak Absen/Ditutup Otomatis).
3. Untuk mencegah rancu lembur pada laporan Payroll sistem, kolom `jam_out` tidak akan diisi waktu pemrosesan Auto-Close, melainkan **dibiarkan kosong (`NULL`)**. 
4. Saat halaman Web Admin maupun HP mendeteksi kehadiran status `'ta'`, UI tidak akan meminta absen pulang (berkedip merah) melainkan menampilkan label **"— (Ditutup Otomatis)"**.

`(Dokumentasi dihasilkan dan diperbarui otomatis oleh Asisten Antigravity pada 22/02/2026)`
