# Dokumentasi Sistem Deteksi Wajah & Liveness (Android)

Sistem "Kotak Deteksi Wajah" (_Face Detection Bounding Box_) merupakan komponen keamanan pilar untuk validasi *Liveness* (Antipemalsuan) yang diimplementasikan pada aplikasi Android K3Guard. Komponen pintar `GlobalFaceDetectionOverlay` ini dirancang secara dinamis agar bisa beradaptasi di berbagai layar utama (Absensi, Patroli, dan Master Wajah) walau menggunakan satu pondasi kode yang sama.

Berikut adalah alur cara kerja sistem overlay kontak deteksi wajah secara komprehensif:

## 1. Inisiasi Mode Radar (Camera Analysis)
Ketika kamera terbuka melalui `GlobalCameraManager.kt`, fungsi *CameraX* tidak sekadar menampilkan video murni, melainkan juga ditenagai jalur paralel bernama `ImageAnalysis`. 
Sistem _ImageAnalysis_ ini memotong video _real-time_ dan mengirimkan jepretan tipis *(proxy)* ke **Google ML Kit Face Detection API** secara intensif setiap `300` milidetik (diatur via *throttle* agar suhu perangkat keras tetap stabil).

## 2. Pemetaan Informasi Geometris Wajah 
Setiap kali ML Kit sukses mendeteksi adanya wajah (`faces.size > 0`) di lensa kamera, ML Kit mengeluarkan data koordinat absolut (titik pixel mentah) dalam bentuk variabel `Face`. ML Kit mengetahui secara pasti lokasi koordinat ujung kepala atas, ujung dagu, dan telinga kiri/kanan yang terbungkus di dalam properti `.boundingBox`. 

## 3. Jembatan Koordinat (Scaling & Mapping)
Sensor resolusi kamera seringkali berbeda dengan ukuran kanvas layar HP (misalnya sensor 4000x3000 piksel sementara layar hanya 1080x2400 piksel). Agar koordinat deteksi tidak meleset, `GlobalFaceDetectionOverlay.kt` menjalankan kalkulasi matematis bernama **`mapBoundingBoxToView`** setiap kali rendering:
- **Pengecekan Orientasi:** Memperhatikan apakah posisi *potrait/landscape*.
- **Kalkulasi Skala:** Mencari skala pengecilan (`scale`) paling proporsional tanpa membuat kotak terlihat oval/gepeng (metode *FILL_CENTER*).
- **Penyesuaian Margin:** Mengkoreksi offset *blank space* margin tak kasat mata (`offsetX` / `offsetY`).
- **Efek Cermin (Mirroring):** Jika kamera depan (`isFrontCamera`) menyala, bidang *Left* dan *Right* otomatis ditukar terbalik agar sinkron dengan gerakan alami pengguna. Tanpa ini, pergerakan kotak akan berlawanan arah dari wajah pengguna.

## 4. Melukis Bingkai Pelacak (Canvas DrawScope)
UI dalam mode Compose ini kemudian memanggil fungsi `drawFaceCornerBox` pada area Canvas, melukis garis siku-siku patah yang menyiku di empat sudut (kiri-atas, kanan-atas, kiri-bawah, dan kanan-bawah). 
Dilengkapi juga dengan animasi proporsional seperti `animateFloat` dan `PulseScale`. Apabila pengguna dinyatakan "Sukses", mesin Pulse akan menyulap kotak tersebut agar **berdenyut lebih besar (1.05x lipat)** bak gerakan bernapas.

## 5. Dinamika Warna & Siklus ScanPhase antar Layar
Warna pigmen (`animatedColor`) kotak berjalan adaptif dioperasikan oleh alur _State Management_ tersentral melalui enum `ScanPhase`. Berikut adalah adaptasi fungsinya di 3 layar sistem:

### A. Layar Absensi Biasa (`AbsensiScreen.kt`)
Berfokus sangat kuat pada Liveness tantangan:
- 🟥 **Merah (`FOCUS_FACE`)**: Kamera baru mendeteksi muka, posisi "standby" menunggu _Verify Face backend_ memberikan hasil sukses.
- 🟩 **Hijau (`BLINK_EYE / TURN_HEAD`)**: Backend meloloskan verifikasi wajah asli, warnanya Hijau menuntun instruksi tantangan (misal: "Kedipkan mata sekarang"). Terdapat pergerakan denyut (*pulse*).
- 🤍 **Putih (`SAVING`)**: Tantangan berhasil diselesaikan dengan baik, sistem mengunci aksi dan siap mengunggah titik presensi.
- 🟥 **Merah Penuh (Failed Lock)**: Jika pengguna terlalu banyak gagal verifikasi atau memalsukan wajah. Layar diblokir memicu _BlockingInfoScreen_.

### B. Layar Absen Patroli (`PatroliScreen.kt`)
Berisi sistem lapisan tambahan yang kompleks seputar "Batas / Keliling Geografis":
- Liveness awal persis seperti Layar Absensi di atas, namun setelah *check-in* blok pertama berhasil, wajah *overlay* berganti ke fase `ScanPhase.PATROLI_MODE`.
- 🟦 **Biru Muda / Sian (`PATROLI_MODE`)**: Kotak *bounding box* berubah warna indikator radar Patroli menjadi Sian. Perangkat otomatis memutar lensa menjadi _Back Camera_ (Kamera Belakang).
- 🎲 **Random Swafoto Check**: Sistem secara asinkron bisa melempar nilai acak (_Math Random_) terhadap 1 dari semua titik (Misal: Rute gedung A, B, C. Sistem memilih gedung C). 
Saat Satpam memindai dan menekan daftar gedung C (yang terpilih), UI akan kembali ke _Force Front Camera_ (Kamera Depan) dan memaksa status *overlay* ke mode _Selfie_, menghindari kecurangan satpam hanya memotret tempat tanpa fisik di lokasi.
- ⏸️ **Auto-Pause Liveness**: Saat layar memunculkan Modal Teguran Keras / Sanksi Disiplin (misalnya akibat lupa scan titik/Terlewat Jadwal), proses _ImageAnalysis_ pendeteksi wajah dan liveness (mata/kepala) akan otomatis mengalami _return early_ (menjeda memori) di _LaunchedEffect_ agar *camera observer* tidak menembak *error failure* secara gaib sewaktu pengguna sedang membaca peringatan.

### C. Layar Perekaman Master Wajah (`MasterWajahScreen.kt`)
Berbeda dengan "Anti-Pemalsuan", layar ini berfungsi dominan sebagai **Mode Koleksi Studio/Pemotretan**:
- Algoritma meniadakan seluruh proses Tantangan Liveness (Tidak perlu melotot / kedip).
- Pemilihan Warna *Derived State* Murni: Saat wajah belum nampak sempurna = Merah (`FOCUS_FACE`). Sewaktu sudah *fit in* = Hijau Stabil (`SUCCESS`) tanpa pergerakan kedut *Pulse*.
- Mode Kekerapan 5x: Memerlukan 5 foto sudut wajah (Depan, Kiri, Kanan, Atas, Bawah). 
- Setelah `capturedBitmaps.size == 5` terpenuhi, mesin merubah sudut pinggiran kotak seketika menjadi 🤍 **Putih Statis (`SAVING`)** mengisyaratkan pengunggahan data mutlak secara final ke server.

Kesimpulannya, arsitektur `GlobalFaceDetectionOverlay` dan `GlobalCameraManager` memiliki reaktivitas "Bunglon" yang sangat baik. *State Management Component* Compose mendalangi semua alur interaksi futuristik berbasis AI ini di dalam 1 naungan *file* yang sangat ter-usabilitas.
