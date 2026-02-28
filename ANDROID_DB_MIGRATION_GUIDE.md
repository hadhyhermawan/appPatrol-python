# Panduan Migrasi / Perubahan Skema Database Android

Dokumen ini berisi daftar perubahan struktur dan penamaan kolom di database (terutama `patrol` MySQL) yang memengaruhi aplikasi Android. Tim pengembang Android wajib menyesuaikan model data (DTO) dan parameter request API berdasarkan daftar perubahan di bawah ini pada versi aplikasi (APK) rilisan berikutnya.

**CATATAN PENTING**: 
Untuk menjaga kompatibilitas aplikasi Android yang sudah _live_ (berjalan) di Play Store saat ini, endpoint API *Legacy* (contoh: secara default di `ops_legacy.py`) telah dikonfigurasi menggunakan teknik **Data Mapping**. Artinya, _request_ dan _response_ JSON untuk aplikasi versi lama akan tetap dipaksakan mengikuti nama lama, meskipun di database utama (MySQL) nama kolomnya sudah diubah.

Penyesuaian di Android hanya wajib dilakukan jika aplikasi akan membaca struktur Endpoint API versi terbaru/modern (`v2`), bukan endpoint legacy.

---

## 1. Modul Pengaturan Lalu Lintas (TURLALIN)

**Latar Belakang Perubahan:**
Sebelumnya, terdapat ambiguitas pada penamaan properti pencatat kendaraan, di mana *NIK petugas yang mencatat masuk* hanya dinamakan `nik` (seolah merepresentasikan identitas kendaraan atau parameter global tak spesifik), sedangkan petugas yang mencatat keluar dinamakan `nik_keluar`.

Untuk memperjelas konteks dan standardisasi sistem, penamaan `nik` akan diubah secara eksplisit menjadi `nik_masuk`.

### Rincian Perubahan Tabel: `turlalin`

> **✅ STATUS IMPLEMENTASI DATABASE: SELESAI (28 Feb 2026)**
> - Kolom MySQL `nik` berhasil dialter menjadi `nik_masuk`.
> - Object Relational Mapping (ORM) SQLAlchemy di backend sudah diadaptasi dengan `@property` fallback ke `nik` agar API Android yang lama (`ops_legacy.py` / App v1) tidak *Force Close*.
> - Semua _records_ lama beserta riwayat presensinya utuh dan aman!


| Kolom Lama (Saat ini) | Tipe Data | Perubahan Baru | Keterangan / Konteks |
| :--- | :--- | :--- | :--- |
| `nik` | `char(18)` | **`nik_masuk`** | Merupakan NIK petugas (Satpam) yang melakukan pencatatan / scan saat kendaraan baru **Masuk**. |
| `nik_keluar` | `char(18)` | (Tidak berubah) | NIK petugas yang melakukan pencatatan saat kendaraan **Keluar**. |
| `foto` | `varchar(255)`| (Tidak berubah) | Foto bukti kendaraan saat **Masuk**. |
| `foto_keluar` | `varchar(255)`| (Tidak berubah) | Foto bukti kendaraan saat **Keluar**. |
| `jam_masuk` | `datetime` | (Tidak berubah) | Waktu kendaraan **Masuk**. |
| `jam_keluar` | `datetime` | (Tidak berubah) | Waktu kendaraan **Keluar**. |

---

### Penyesuaian Tim Pengembang Android

Saat rilis aplikasi versi berikutnya dan berpindah untuk mengkonsumsi API Turlalin terbaru, pastikan untuk mengubah Serialized Name (pemetaan JSON) pada `Data Class` Kotlin di proyek sumber Android.

**Sebelum (TurlalinResponse.kt):**
```kotlin
data class TurlalinResponse(
    // ...
    @SerializedName("nik")
    val nikMasuk: String,
    
    @SerializedName("nik_keluar")
    val nikKeluar: String?,
    // ...
)
```

**Sesudah (Versi Update Selanjutnya):**
```kotlin
data class TurlalinResponse(
    // ...
    @SerializedName("nik_masuk")    // <-- UBAH BAGIAN INI
    val nikMasuk: String,
    
    @SerializedName("nik_keluar")
    val nikKeluar: String?,

    @SerializedName("nama_petugas_masuk") // <-- UBAH BAGIAN INI DARI nama_satpam_masuk
    val namaPetugasMasuk: String?,

    @SerializedName("nama_petugas_keluar") // <-- UBAH BAGIAN INI DARI nama_satpam_keluar
    val namaPetugasKeluar: String?,
    // ...
)
```

**Penyesuaian Endpoint Form Data (POST):**
Selain respons (GET), pastikan _form fields_ yang dikirim melalui `ApiService.kt` untuk menyimpan data Turlalin Masuk juga disesuaikan jika API meminta format _key_ JSON baru dari:
- `nik` -> menjadi -> `nik_masuk`

*(Tabel dimodifikasi secara berkala di dokumen ini jika terdapat perubahan struktur).*

---

## 4. Modul Surat Masuk & Surat Keluar

**Latar Belakang Perubahan:**
Istilah "Satpam" sebagai predikat log dicabut dan diselaraskan agar universal menggunakan _petugas_ untuk menghindari kebingungan antar divisi maupun skalabilitas ke depan.

### Rincian Perubahan Tabel: `surat_masuk` & `surat_keluar`

> **✅ STATUS IMPLEMENTASI DATABASE: SELESAI (28 Feb 2026)**
> - Kolom MySQL `nik_satpam` dan `nik_satpam_pengantar` berhasil dialter menjadi `nik_petugas` dan `nik_petugas_pengantar` di kedua tabel.
> - ORM SQLAlchemy di backend (`models.py`) ditambahkan `@property` fallback alias agar APK Android rilisan _current_ saat ini tidak terputus dan tetap bisa menembak field lama tanpa _force close_.

| Kolom Lama (Saat ini) | Tipe Data | Perubahan Baru | Keterangan / Konteks |
| :--- | :--- | :--- | :--- |
| `nik_satpam` | `char(18)` | **`nik_petugas`** | NIK Petugas jaga yang bertugas mengelola fisik surat dan data entry-nya. |
| `nik_satpam_pengantar` | `char(18)` | **`nik_petugas_pengantar`** | NIK Petugas yang mendistribusikan / mengamankan fisik suratnya kepada pihak internal. |
| `foto` | `varchar(255)` | **`foto_surat`** | Gambar / lampiran khusus untuk fisik surat, agar tidak tertukar dengan foto wajah penerima. |

### Penyesuaian Tim Pengembang Android

Saat rilis aplikasi versi berikutnya, ubah _Data Class_ atau API Call POST form fields yang dikirim / diterima dari Backend.

**Sebelum (Contoh Response JSON / Request Call):**
```kotlin
@SerializedName("nik_satpam")
val nikSatpam: String

@SerializedName("nik_satpam_pengantar")
val nikSatpamPengantar: String?

@SerializedName("foto")
val foto: String?
```

**Sesudah (Versi Pindahaan Berikutnya):**
```kotlin
@SerializedName("nik_petugas")
val nikPetugas: String

@SerializedName("nik_petugas_pengantar")
val nikPetugasPengantar: String?

@SerializedName("nama_petugas_penerima") // <-- UBAH BAGIAN INI DARI nama_satpam
val namaPetugasPenerima: String?

@SerializedName("nama_petugas_pengantar") // <-- UBAH BAGIAN INI DARI nama_pengantar
val namaPetugasPengantar: String?

@SerializedName("foto_surat")
val fotoSurat: String?
```

---

## 2. Modul Tamu (Visitor Log)

**Latar Belakang Perubahan:**
Untuk mempertegas peran sistem penjagaan yang menangani log kedatangan dan kepulangan tamu (pengunjung), field data `nik_satpam` dan `nik_satpam_keluar` telah diubah untuk mengacu pada terminologi yang lebih general dan komprehensif, yakni _petugas_.

### Rincian Perubahan Tabel: `tamu`

> **✅ STATUS IMPLEMENTASI DATABASE: SELESAI (28 Feb 2026)**
> - Kolom MySQL `nik_satpam` dan `nik_satpam_keluar` berhasil dialter menjadi `nik_petugas_masuk` dan `nik_petugas_keluar`.
> - ORM SQLAlchemy di backend (`models.py`) ditambahkan `@property` fallback alias agar APK Android rilisan _current_ saat ini tidak terputus dan tetap bisa menembak field lama tanpa _force close_.

| Kolom Lama (Saat ini) | Tipe Data | Perubahan Baru | Keterangan / Konteks |
| :--- | :--- | :--- | :--- |
| `nik_satpam` | `char(18)` | **`nik_petugas_masuk`** | NIK Petugas jaga yang melakukan pendaftaran awal ketika Tamu masuk/datang. |
| `nik_satpam_keluar` | `char(18)` | **`nik_petugas_keluar`** | NIK Petugas jaga yang melakukan konfirmasi / tap-out ketika Tamu sudah keluar/pulang. |

### Penyesuaian Tim Pengembang Android

Saat rilis aplikasi versi berikutnya, ubah _Data Class_ atau API Call POST form fields yang dikirim / diterima dari Backend.

**Sebelum (Contoh Response JSON / Request Call):**
```kotlin
@SerializedName("nik_satpam")
val nikSatpamMasuk: String

@SerializedName("nik_satpam_keluar")
val nikSatpamKeluar: String?
```

**Sesudah (Versi Pindahaan Berikutnya):**
```kotlin
@SerializedName("nik_petugas_masuk")
val nikPetugasMasuk: String

@SerializedName("nik_petugas_keluar")
val nikPetugasKeluar: String?
```

---

## 3. Modul Safety Briefing

**Latar Belakang Perubahan:**
Sama halnya dengan `turlalin`, penggunaan kolom `nik` yang generic kurang deskriptif untuk mendata petugas _security_ yang sedang melakukan laporan rutin. Kolom tersebut telah diubah menjadi `nik_petugas` agar fungsi pelapornya lebih spesifik.

### Rincian Perubahan Tabel: `safety_briefings`

> **✅ STATUS IMPLEMENTASI DATABASE: SELESAI (28 Feb 2026)**
> - Kolom MySQL `nik` berhasil dialter menjadi `nik_petugas`.
> - ORM SQLAlchemy di backend (`models.py`) ditambahkan `@property` alias untuk menangkap request `nik` dari Apps Android saat ini.

| Kolom Lama (Saat ini) | Tipe Data | Perubahan Baru | Keterangan / Konteks |
| :--- | :--- | :--- | :--- |
| `nik` | `char(18)` | **`nik_petugas`** | NIK Karyawan (Satpam) yang meng-upload form safety briefing. |

### Penyesuaian Tim Pengembang Android

Saat rilis aplikasi versi berikutnya, sesuaikan DTO pada `SafetyBriefingResponse.kt` (maupun _form data request_-nya).

**Sebelum:**
```kotlin
@SerializedName("nik")
val nik: String
```

**Sesudah (Versi Update Selanjutnya):**
```kotlin
@SerializedName("nik_petugas")
val nikPetugas: String
```

---

## 5. Fitur Logo Vendor Dinamis (Beranda)

**Latar Belakang Perubahan:**
Aplikasi versi lama menggunakan logo bawaan k3guard secara statis (`R.drawable.logo`) pada layar Beranda Android. Sejalan dengan fitur White-Label sistem SaaS, sekarang API Beranda sanggup melempar informasi `vendor_logo` milik Karyawan yang sedang *login*.

### Endpoint: `/api/android/beranda`

> **✅ STATUS IMPLEMENTASI DATABASE & API: SELESAI (28 Feb 2026)**
> - Kolom MySQL `logo` sudah tersedia di tabel `vendors`.
> - Payload JSON respon API Beranda saat ini telah diinjeksi dengan URL logo *("vendor_logo")* selain profil karyawan.

### Penyesuaian Tim Pengembang Android

Saat rilis aplikasi versi berikutnya, pastikan fitur logo vendor ini sudah di-*uncomment* atau dieksekusi pemanggilannya pada UI _Compose_ Beranda (file `BerandaScreen.kt` dan `HeaderSection.kt`), seperti yang sudah dimodifikasi pada _source code_ di staging (VPS).

**Penyesuaian Model DTO:**
Pada model response `BerandaResponse.kt` pastikan properti baru ini ditangkap.

**Sebelum (BerandaResponse.kt):**
```kotlin
data class KaryawanData(
    // ...
    @SerializedName("kode_jadwal") val kode_jadwal: String?,
    @SerializedName("sisa_hari_masa_aktif_kartu") val sisa_hari_masa_aktif_kartu: Int?
)
```

**Sesudah:**
```kotlin
data class KaryawanData(
    // ...
    @SerializedName("kode_jadwal") val kode_jadwal: String?,
    @SerializedName("sisa_hari_masa_aktif_kartu") val sisa_hari_masa_aktif_kartu: Int?,
    @SerializedName("vendor_logo") val vendor_logo: String? // <-- PROPERTI BARU
)
```

---

## 6. Modul Barang

**Latar Belakang Perubahan:**
Istilah "Satpam" sebagai predikat log dicabut dan diselaraskan agar universal menggunakan _petugas_ untuk menghindari kebingungan antar divisi.

### Rincian Perubahan Tabel: `barang_masuk` & `barang_keluar`

> **✅ STATUS IMPLEMENTASI DATABASE: SELESAI**
> - Response API Backend sudah tidak lagi menggunakan `nik_satpam` atau `nama_satpam`.

### Penyesuaian Tim Pengembang Android

**Sebelum (BarangResponse.kt):**
```kotlin
@SerializedName("nik_satpam") val nikSatpamBarang: String?,
@SerializedName("nama_satpam") val namaSatpam: String?,
@SerializedName("nik_penyerah") val nikPenyerah: String?,
@SerializedName("nama_penyerah") val namaPenyerah: String?,
```

**Sesudah (Versi Pindahaan Berikutnya):**
Jika di kemudian hari struktur database ikut dirubah atau response REST API sudah dipertegas, pastikan Data Class menyesuaikan _key_ terbarunya ke:
```kotlin
// Contoh penyesuaian jika diperlukan di masa mendatang
@SerializedName("nik_petugas") val nikPetugas: String?
@SerializedName("nama_petugas") val namaPetugas: String?
```
*(Catatan: Modul barang pada API Legacy sudah menangani mapping ini dengan baik).*
