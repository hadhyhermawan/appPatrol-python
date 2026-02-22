# Dokumentasi: `check_jam_kerja_status`

> **File:** `app/routers/tamu_legacy.py`  
> **Digunakan oleh:** Tamu, Barang, Surat Masuk, Surat Keluar, Turlalin, Safety Briefing

---

## Tujuan

Fungsi validasi terpusat yang memastikan seorang karyawan **berhak mengakses atau menginput data operasional** berdasarkan tiga kondisi utama:

1. Sudah absen masuk & belum absen pulang
2. Memiliki jadwal kerja yang aktif hari ini
3. Waktu saat ini berada dalam rentang jam kerja shift-nya

---

## Signature

```python
def check_jam_kerja_status(db: Session, karyawan: Karyawan) -> dict:
```

### Parameter

| Parameter | Tipe | Keterangan |
|---|---|---|
| `db` | `Session` | SQLAlchemy database session |
| `karyawan` | `Karyawan` | Object model karyawan yang sedang login |

### Return Value

```python
# Berhasil
{"status": True}

# Gagal
{"status": False, "message": "Pesan error untuk user"}
```

---

## Alur Validasi

```
START
  │
  ▼
[Gate 1] Cek Presensi Hari Ini
  - nik = karyawan.nik
  - tanggal = hari ini
  - jam_in IS NOT NULL
  - jam_out IS NULL
  │
  ├── Tidak ditemukan?
  │       │
  │       ▼
  │   [Gate 1b] Cek Lintas Hari (kemarin)
  │     - tanggal = kemarin
  │     - lintashari = 1
  │     - jam_in IS NOT NULL
  │     - jam_out IS NULL
  │       │
  │       ├── Masih tidak ada?
  │       │       ▼
  │       │   ❌ RETURN False
  │       │   "Anda belum absen masuk atau sudah absen pulang."
  │       │
  │       └── Ditemukan → lanjut ke Gate 2
  │
  └── Ditemukan → lanjut ke Gate 2
  │
  ▼
[Gate 2] Cek Jadwal Shift (via get_jam_kerja_karyawan)
  Prioritas:
    0. PresensiJamkerjaBydateExtra  ← Extra/Lembur/Double Shift
    1. SetJamKerjaByDate            ← Tukar Shift
    2. SetJamKerjaByDay             ← Jadwal Rutin Personal
    3. PresensiJamkerjaBydept       ← Default Departemen
  │
  ├── Tidak ada jadwal?
  │       ▼
  │   ❌ RETURN False
  │   "Anda tidak memiliki jadwal kerja hari ini."
  │
  └── Ada jadwal → lanjut ke Gate 3
  │
  ▼
[Gate 3] Cek Window Waktu
  - start_dt = presensi.tanggal + jam_masuk
  - end_dt   = presensi.tanggal + jam_pulang
  - Jika end_dt <= start_dt → end_dt += 1 hari (handle lintas hari)
  │
  ├── now < start_dt ATAU now > end_dt?
  │       ▼
  │   ❌ RETURN False
  │   "Di luar jam kerja shift HH:MM–HH:MM."
  │
  └── Dalam window
          ▼
      ✅ RETURN True
```

---

## Pesan Error

| Kondisi | Pesan |
|---|---|
| Belum absen masuk / sudah absen pulang | `"Anda belum absen masuk atau sudah absen pulang."` |
| Tidak ada jadwal kerja hari ini | `"Anda tidak memiliki jadwal kerja hari ini."` |
| Di luar rentang jam shift | `"Di luar jam kerja shift HH:MM–HH:MM."` |

---

## Cara Penggunaan

```python
from app.routers.tamu_legacy import check_jam_kerja_status

@router.get("/endpoint-saya")
async def endpoint_saya(user: CurrentUser = Depends(...), db: Session = Depends(get_db)):
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()

    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        # Untuk GET → return data kosong
        return {"status": True, "message": shift_check["message"], "data": []}
        # Untuk POST → raise error
        # raise HTTPException(status_code=403, detail=shift_check["message"])
```

---

## Fitur yang Menggunakan Fungsi Ini

| Fitur | GET | POST Store | POST Update/Keluar |
|---|---|---|---|
| **Tamu** | ✅ | ✅ | ✅ |
| **Barang Masuk/Keluar** | ✅ (delegate) | ✅ (delegate) | ✅ (delegate) |
| **Safety Briefing** | ✅ | ✅ | — |
| **Surat Masuk** | ✅ | ✅ | ✅ |
| **Surat Keluar** | ✅ | ✅ | ✅ |
| **Turlalin** | ✅ | ✅ | ✅ |

> **Catatan:** Barang menggunakan delegate langsung ke fungsi ini via:
> ```python
> from app.routers.tamu_legacy import check_jam_kerja_status as _check
> return _check(db, karyawan)
> ```

---

## Catatan Teknis

### Handle Shift Lintas Hari
Shift malam yang dimulai kemarin (misal 22:00–06:00) ditangani di dua tempat:
- **Gate 1b:** Cek `presensi` dengan `tanggal = kemarin` dan `lintashari = 1`
- **Gate 3:** `end_dt` ditambah 1 hari jika `end_dt <= start_dt`
- Base date untuk kalkulasi window diambil dari `presensi.tanggal` (bukan `datetime.now()`)

### Handle Extra/Lembur
Karyawan dengan jadwal extra (lembur/double shift) dicek di **prioritas 0** pada `get_jam_kerja_karyawan`, sebelum jadwal reguler apapun.

### Exception Handling
Gate 3 dibungkus dalam `try/except` — jika parsing waktu gagal (format tidak dikenal), validasi **dilewati** dan dianggap valid (`status: True`). Ini mencegah karyawan terkunci karena bug format data.

---

## Riwayat Perubahan

| Tanggal | Perubahan |
|---|---|
| 2026-02-20 | Ditambahkan Gate 1b (lintas hari) |
| 2026-02-20 | Ditambahkan Extra shift (prioritas 0) di `get_jam_kerja_karyawan` |
| 2026-02-20 | Fix kalkulasi window lintas hari menggunakan `presensi.tanggal` |
| 2026-02-20 | Pesan error dipersingkat untuk UI Android |
| 2026-02-20 | Dijadikan satu sumber untuk semua fitur operasional |

---

## Alur Darurat Screen

> **File Backend:** `app/routers/emergency_legacy.py`  
> **File Android:** `ui/darurat/DaruratScreen.kt`, `ui/darurat/viewmodel/DaruratViewModel.kt`

### Saat Screen Dibuka (`init → refreshAvailability`)

```
DaruratScreen dibuka
        │
        ▼
DaruratViewModel.refreshAvailability()
        │
        ▼
BerandaRepository.getBeranda()  ← GET /api/android/beranda
        │
        ▼
Cek response.data.presensi_hari_ini:
  hasCheckIn   = jam_in tidak null/blank
  hasCheckOut  = jam_out tidak null/blank
  hasLintasHari = lintashari == "1"   ← hanya "1", bukan "0" atau lainnya
        │
        └─ canTrigger = (hasCheckIn OR hasLintasHari) AND NOT hasCheckOut
                │
                ├─ TRUE  → Tombol SOS AKTIF
                │          "Tombol darurat aktif karena absen masuk terdeteksi."
                ├─ hasCheckOut=true → Tombol NONAKTIF
                │          "Tombol darurat nonaktif setelah absen pulang."
                └─ Lainnya → Tombol NONAKTIF
                           "Tombol darurat akan aktif setelah absen masuk."
```

### Saat Tombol SOS Ditekan

```
User tap tombol SOS
        │
        ▼
PanicConfirmDialog ("Konfirmasi Bahaya")
        ├─ Batal → tutup dialog
        └─ KIRIM SOS
                │
                ├─ triggerVibration(context)   ← Getar 200ms
                ├─ playAlarmSound(context)     ← Play alarm sound
                └─ viewModel.triggerEmergency("intrusi", null)
                        │
                        ▼
                POST /api/android/emergency/trigger
                {
                  branch_code, user_id, timestamp,
                  location: null, alarm_type: "intrusi"
                }
```

### Backend: `POST /api/android/emergency/trigger`

```
Request diterima
        │
        ▼
[Gate 1] Cek NIK valid
        │
        ▼
[Gate 2] Cek Presensi Aktif
  - Hari ini: jam_in ada, jam_out null
  - Lintas hari: kemarin, lintashari=1, jam_out null
        │ Gagal → HTTP 403
        │
        ▼
[Gate 3] Cooldown Check (60 detik)
  - Cek trigger terakhir dari NIK ini
  - Jika < 60 detik → status: false + retry_after
        │
        ▼
[Gate 4] Ambil nama_cabang dari tabel Karyawan/Cabang
        │
        ▼
Simpan ke tabel emergency_alerts
        │
        ▼
Broadcast Socket.IO "emergency_broadcast"
  { id, type, lokasi, branch, branch_name, user, nik, timestamp }
        │
        ▼
Response:
  {
    status: true,
    message: "Alarm darurat berhasil dikirim!",
    alarm_id, branch_code, branch_name,
    alarm_type, retry_after: 60
  }
```

### Penanganan Response di Android

| Kondisi | Pesan | Tombol |
|---|---|---|
| `status=true` | `statusMessage` tampil hijau | Tetap aktif |
| `status=false` + 403 | `errorMessage` + `canTrigger=false` | Nonaktif |
| `status=false` + cooldown | `errorMessage` + countdown | Tetap aktif |
| HTTP Error | `errorMessage` dari `errorBody` | Tetap aktif |

### Perbaikan yang Diterapkan (2026-02-20)

| # | Masalah | Fix |
|---|---|---|
| 1 | `lintashari` `"0"` dianggap aktif | Ubah ke `== "1"` |
| 2 | Backend tidak cek absen masuk | Tambah Gate 2 (presensi aktif + lintas hari) |
| 3 | `branch_name` selalu `""` | Query dari tabel `Cabang`/`Karyawan` |
| 4 | Tidak ada rate limiting | Tambah cooldown 60 detik |

