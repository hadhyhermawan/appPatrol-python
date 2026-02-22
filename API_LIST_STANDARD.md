# SOP: Standar Pemanggilan dan Respons API Get List (List Data)

Dokumen ini menjelaskan Standar Operasional Prosedur (SOP) untuk membuat endpoint API jenis **Get List** (membaca daftar data) pada sistem `appPatrol-python`. 
Tujuan standar ini adalah memastikan konsistensi format respons antara Backend (Python) dan Frontend/Mobile (Android), sehingga memudahkan maintenance, parsing data (menggunakan GSON/sejenisnya), dan meminimalkan manipulasi data di sisi Client-side.

## 1. Aturan Validasi Akses (Ototorisasi & Penjadwalan)

Setiap endpoint yang menampilkan data operasional harian (seperti daftar Tamu, daftar Turlalin, dll) yang dibatasi oleh sesi shift petugas wajib mengimplementasikan validasi jadwal shift.

**Hal yang divalidasi:**
1. Karyawan harus tercatat di database (`Karyawan.nik`).
2. Karyawan wajib memiliki jadwal shift operasional pada hari yang bersangkutan.
3. Karyawan wajib sudah melakukan Absen Masuk dan *belum* melakukan Absen Pulang.
4. Permintaan API (Request) dilakukan pada rentang waktu shift tersebut.

**Contoh Implementasi di Endpoint (Python FastAPI):**
```python
from app.routers.tamu_legacy import check_jam_kerja_status

@router.get("/nama-entitas")
async def list_entitas(
    limit: int = 20,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Tarik Data Karyawan
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")

    # 2. Lakukan Pengecekan Shift Absensi
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        # WAJIB RETURN STATUS: True dan data: [] jika hanya error diluar jam shift
        # Ini mencegah layar Android menjadi Error 404/Crash, melainkan tampil "Belum Ada Data"
        return {
            "status": True, 
            "message": shift_check["message"], 
            "nik_satpam": karyawan.nik,
            "kode_cabang": karyawan.kode_cabang,
            "data": []
        }

    # 3. Lanjutkan logika Query Data...
    kode_cabang = karyawan.kode_cabang
```

## 2. Aturan Struktur Payload Respons (JSON)

Root struktur respons API wajib minimal memiliki 4 kunci utama:
- `status`: (Boolean) Status sukses tidaknya request.
- `nik_satpam`: (String) NIK user yang request.
- `kode_cabang`: (String) Kode cabang dari user yang request.
- `data`: (Array of Object) List dari objek data utama.

Setiap **Object dalam Data** wajib menyertakan semua properti yang didefinisikan dalam Data Class Android secara utuh, bukan hanya sebagian.
Jika nilainya kosong, kembalikan atribut tersebut dengan nilai `null` (di Python: `None`). **JANGAN LUPA** mengurai URL gambar secara absolute (harus berawalan `http/https`).

**Contoh Payload Standar:**
```json
{
  "status": true,
  "nik_satpam": "180XXX",
  "kode_cabang": "JKT01",
  "data": [
    {
      "id": 1,
      "nomor_polisi": "B 1234 CD",
      "keterangan": "Tamu VIP",
      "foto": "https://frontend.k3guard.com/api-py/storage/turlalin/xxx.jpg",
      "foto_keluar": null,
      "jam_masuk": "2026-02-20 08:30:00",
      "jam_keluar": null,
      "nik": "180XXX",
      "nik_keluar": null,
      "nama_satpam_masuk": "Budi Santoso",
      "nama_satpam_keluar": null,
      "created_at": "2026-02-20 08:30:00",
      "updated_at": "2026-02-20 08:30:00"
    }
  ]
}
```

## 3. Aturan Pengurutan (Sorting) Data

Proses *sorting* (pengurutan) **HARUS** dilakukan dan ditentukan di sisi Backend (Query Database). **Client App (Android / Web) TIDAK BOLEH mem-bypass atau melakukan re-sorting.**

**Prioritas Standar Pengurutan (Contoh: Buku Tamu / Keluar-Masuk):**
1. Data **Aktif/Proses** (Seperti Tamu yang belum check out atau `jam_keluar IS NULL`) **Wajib tampil PALING ATAS**.
2. Data diurutkan berdasarkan **Terbaru Masuk** (Waktu Masuk / Created At).

**Contoh Logic sorting di SQLAlchemy:**
```python
# .isnot(None) mengevaluasi jika jam_keluar=Null menjadi prioritas 0 (teratas saat ASC).
# desc(entitas.jam_masuk) menjadi kriteria sorting kedua (yang terbaru masuk).

items = db.query(Entitas)\
        .filter(Entitas.kode_cabang == kode_cabang)\
        .order_by(
            Entitas.jam_keluar.isnot(None),  # Null (Belum Selesai) Tampil Teratas
            desc(Entitas.jam_masuk)          # Terbaru Masuk Tampil Teratas
        ).limit(limit).all()
```

## 4. Keuntungan Standar Ini
- **Durable:** Validasi absensi yang kokoh mencegah orang tak bertanggung jawab mengisi list data.
- **Konsisten:** *Mobile Developer* bisa langsung me-*mapping* Respons ke Data Model Class tanpa manipulasi objek lanjutan di perangkat.
- **Client-light:** Sorting dari sisi SQL mengurangi beban *processing* memori pada smartphone pengguna.
