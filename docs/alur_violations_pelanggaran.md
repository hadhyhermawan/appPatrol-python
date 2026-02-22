# Panduan Alur Deteksi Pelanggaran (Scan Violations)

Dokumen ini menjelaskan alur teknis mengenai bagaimana sistem **appPatrol** (Backend Python) mendeteksi dan mencatat pelanggaran karyawan secara otomatis, khususnya karyawan yang **Tidak Hadir (Alpha)** dan **Terlambat**.

Fitur ini melayani _endpoint_ `GET /api/security/violations` yang digunakan oleh halaman admin `https://frontend.k3guard.com/security/violations`.

---

## 1. Konsep Dasar & Perbaikan Utama

Sebelumnya, terdapat ambiguitas data antara laporan HRD (Presensi) dengan laporan bagian Keamanan/Disiplin (Violations). 
- Di **Laporan Presensi**, jika seorang karyawan aktif ("1") sama sekali tidak memiliki riwayat absen pada hari tersebut, akan langsung di-_flag_ sebagai **Alpha (A)**.
- Di **Menu Violations (Legacy)**, pengecekan Alpha sangat berlapis-lapis (menerapkan N+1 _query_ ke tabel `SetJamKerjaByDay`, `SetJamKerjaByDate`, `PresensiJamkerjaBydateExtra`) sehingga seringkali proses validasi ini _timeout/hang_ yang mengakibatkan karyawan tersebut **lolos** dari radar "Tidak Hadir (Alpha)".

**Perbaikan: Penyelarasan Konsep (Sync)**
Untuk menyelaraskan data dengan laporan HRD, kini *Scan Violations* menggunakan logika "Satu Pintu" yang sederhana dan **sangat cepat**:
Karyawan dengan Status Aktif (`status_aktif_karyawan = '1'`) secara naif dianggap **Alpha (Absent)** JIKA:
1. Ia tidak berada dalam _list_ yang telah melakukan "Absen Masuk" hari ini.
2. Cabang tempatnya bekerja tidak sedang dalam status "Hari Libur" (`HariLibur`).

Semua pendeteksian berjalan otomatis dalam satu eksekusi pemuatan halaman (*Auto-sync background*), membuang kebutuhan Admin HRD untuk memencet tombol "Start Scan" secara manual.

---

## 2. Alur Teknis API `get_violations`

Saat halaman `/security/violations` diakses, sistem melakukan *auto-sync* dengan memanggil rutinitas `scan_violations(today, db)`. 
Segala jenis _System-Detected Violations_ (Alpha, Terlambat, Fraud Aplikasi, dsb.) akan seketika di-inject ke tabel Database `violations`.

### A. Mendeteksi Alpha (Tidak Hadir)
1. **Dapatkan Karyawan Aktif:**
   ```python
   q_active_karyawan = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1')
   ```
2. **Keluarkan (Exclude) Karyawan yang Sudah Absen Hari Ini:**
   ```python
   presensi_niks = [p.nik for p, _, _ in presensi_list]
   q_active_karyawan = q_active_karyawan.filter(Karyawan.nik.notin_(presensi_niks))
   ```
3. **Cek Hari Libur Massal (Optimalisasi N+1 Query):**
   ```python
   holidays = db.query(HariLibur).filter(HariLibur.tanggal == date_scan).all()
   holiday_cabang_codes = {h.kode_cabang for h in holidays}
   ```
4. **Vonis Hukuman:** Jika `karyawan.kode_cabang` tidak termuat di dalam daftar Hari Libur, ia dicatat sebagai Pelanggaran "SEDANG" (`ABSENT`).

### B. Mendeteksi Terlambat (Late Check-in)
Menggunakan strategi SQL _Outer Join_ secara massal untuk menghilangkan _N+1 query problem_ agar mencegah _server lag/hang_:

```python
q_presensi = db.query(Presensi, Karyawan, PresensiJamkerja).join(
    Karyawan, Presensi.nik == Karyawan.nik
).outerjoin(
    PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja
).filter(Presensi.tanggal == date_scan)
```

**Perbaikan Perbandingan Waktu (*String Comparison*):**
Di versi lawas, kode membandingkan Waktu Absen `(2026-02-22 08:32:00)` menghadapi Waktu Jadwal `(08:00:00)`. Mengamankan tipe perbandingan antar `String` yang keliru ini adalah dengan secara ketat memotong (`strftime` / `[:8]`) sehingga formatnya berimbang adil: `08:32:00` > `08:00:00`.

---

## 3. Resolusi Error Database MySQL: "Illegal mix of collations"

Pada proses perbaikan, ketika sejumlah ratusan Alpha coba didorong paksa ke tabel Violations, _framework_ **SQLAlchemy tiba-tiba hancur (*crash/query timeout*)**.

Error Output:
`pymysql.err.OperationalError: (1267, "Illegal mix of collations (utf8mb4_general_ci,IMPLICIT) and (utf8mb4_unicode_ci,IMPLICIT) for operation '='")`

**Penyebab:**
Sebuah relasi `INNER JOIN` mendadak gagal dikarenakan bentuk *Character Set / Collation* format identitas karyawan di tabel `violations` (yakni kolom `violations.nik`) tidak identik sama dengan di tabel `karyawan.nik`.
- `karyawan.nik` memakai standar Collation: `utf8mb4_unicode_ci`
- `violations.nik` memakai standar Collation lawas: `utf8mb4_general_ci`

**Solusi Penyelesaian (Fixes):**
Telah dieksekusi secara permanen ke Database menggunakan _SQL Query_ standar melalui skrip python untuk menormalkan struktur kolom:
```sql
ALTER TABLE violations MODIFY nik CHAR(18) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL;
```
Kedua tabel saat ini selaras 100% dan halaman sudah bebas *Crash Database View ERROR*.

---

## 4. Kategori Jenis Pelanggaran (Violation Types)

Berikut pemetaan kode status (*violation_codes*) yang secara otomatis terekstrasi dan dimumculkan di tiket Pelanggaran:

| Kode (*violation_code*) | Label Tipe | Kategori | Penjelasan Deteksi |
| --- | --- | --- | --- |
| `LATE` | Terlambat | RINGAN | Jam "Check-In" lebih besar melampaui "Jam Masuk" Jadwal. |
| `ABSENT` | Tidak Hadir | SEDANG | Belum/Mangkir absen padahal dirinya berstatus karyawan Aktif. |
| `NO_CHECKOUT` | Tidak Absen Pulang | SEDANG | Hari telah berganti namun status `jam_out` masih gantung (Null). |
| `MISSED_PATROL` | Tidak Patroli | SEDANG | (Khusus Dept Security) Hadir namun tidak men-*Tap* poin patroli *NFC*. |
| `OUT_OF_LOCATION` | Di Luar Radius | SEDANG | Menarik jarak Haversine (Longitude, Latitude) meleset jauh dari titik Cabang. |
| `FAKE_GPS` | Fake GPS | BERAT | Ketahuan mengakali lokasi dari Android (melalui menu `/security-reports`/mock locator). |
| `FORCE_CLOSE` | Force Close | SEDANG | Mematikan aplikasi paksa (Swipe tutup app). |
| `ROOTED` | Root Device | BERAT | OS Android terdeteksi di-_root/jailbreak_. |
| `BLOCKED` | Akun Terblokir | BERAT | HRD telah mengisi *record* nonaktif. |

Semua riwayat deteksi pelanggaran di atas otomatis mem-populasi API `get_violations` tanpa admin harus mencari *filter* secara manual.
