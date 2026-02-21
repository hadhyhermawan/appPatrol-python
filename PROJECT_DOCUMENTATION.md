
## 21. Fix Absensi Fallback (NON SHIFT)
- Date: 2026-02-21
- Repo: appPatrol-python
- **Issue**: Karyawan with `lock_jam_kerja = 0` (allowed to change their shift) would send `kode_jam_kerja: null` from the Android app when performing `absen`. The Python backend `POST /api/android/absensi/absen` would default this to `"NS"` and immediately fallback to the first row in `presensi_jamkerja` (which happens to be `0001 - NON SHIFT`), completely ignoring their actual shift schedule on that day.
- **Solution**: Refactored the `get_presensi_hari_ini` scheduling logic into an independent and reusable function `determine_jam_kerja_hari_ini()`. Now, if the frontend sends a `null` or `'NS'` shift, the `absen` endpoint uses this function to calculate the mathematically correct shift for the day (checking `by_date_extra` -> `by_date` -> `by_day` -> `dept` -> `user_default`), ensuring users are accurately recorded according to their schedule (e.g. `0003 - SF SORE`) instead of falsely marked as `NON SHIFT`.
- **Status**: Tested and pushed to remote. Service restarted.

## 22. Fix Android Guest Input Validation & Missing Payload Fields
- Date: 2026-02-21
- Repos: appPatrol-python, GuardSystemApp-src
- **Issue**: Input variables fields *No. Telepon* and *Bertemu Dengan* were not correctly saved into the database when guards submitted newly registered guests from Android apps. Additionally, there was a lack of mandatory validations and number formatting limitations. 
- **Solution**: 
  1. Disabled conflicting routing path `/tamu/` inside `logistik_legacy.py` which was intercepting and parsing via strict camelCase fields (causing snake_case Android arrays to drop). Pointed requests back fully to `tamu_legacy.py`. 
  2. Kotlin UI `TambahTamuScreen.kt` was updated to require all fields dynamically before submitting and limiting the *Phone Number* field strictly to numbers-only (min 11, max 13 digits length).

## 23. Fix Date & Time Mismatches on Web Admin and Android Display
- Date: 2026-02-21
- Repos: apppatrol-admin, GuardSystemApp-src
- **Issue**: Modifying a guest logged-time on the Web dashboard wrongly subtracts -7 hours. Additionally, Android app incorrectly shifts display times ahead by 7 hours (+7) due to a hardcoded logic treating native WIB records identically as zero-offset UTC.
- **Solution**:
  1. Frontend (Next.JS `apppatrol-admin`): Substituted standard Javascript `.toISOString()` timezone-forcing function inside `page.tsx` guest editor with a pure `substring(0, 16)` text parser. Time representations are now maintained as Native local values. Assigned `time_24hr: true` to the Flatpickr properties.
  2. Mobile Frontend (Kotlin): Removed UTC-offset assumptions within `FormatTanggal.kt`. Parsed Android DateTimes normally without converting between TimeZones since the DB serves straightforward raw strings.

## 24. Implement Photo Reload Fallback Feature on Android UI
- Date: 2026-02-21
- Repos: GuardSystemApp-src
- **Issue**: Due to poor network conditions, if an image fails to load initially in `TamuCardStack.kt` (e.g. guest avatar or clicked preview), the photo frame would turn blank with no way for users to manually trigger a retry. Users were forced to navigate outside the page and return just to trigger a recomposition.
- **Solution**: Refactored `AsyncImage` into `SubcomposeAsyncImage` provided by the Coil Compose package. Implemented a `loading` indicator state and an interactive `error` layout featuring a refresh icon. When network fails, the refresh icon prompts users to literally "hit reload", modifying a local URL query parameter suffix (`?retry=SystemTime`) directly, thereby bypassing Coil's local broken cache natively within the view and restarting the image retrieval without needing to leave the screen.
- **Status**: Tested, pushed to github `main`.

## 25. Menyelaraskan UI "Barang/Paket" dengan "Tamu" (Android)
- **Komponen List**: Diperbarui dari `BarangCardStacked` lama menjadi gaya tampilan card minimalis yang sama dengan Tamu (dengan status bar/aksen vertikal, avatar bula, & font senada).
- **SubcomposeAsyncImage**: Thumbnail foto Barang kini punya kapabilitas memuat ulang secara mandiri lewat sentuhan ikon **"Refresh (Tap Reload)"** bila di-klik layaknya Tamu.
- **Warna & Aksi Tombol**: Mengubah _Floating Action Button_ untuk Tambah (+) dan merombak tombol "Ambil Barang" tampilannya identik kuat (Warna Hijau Green) bersama icon *log out*.
- **Camera Viewfinder**: Kamera untuk menu "Tambah Barang" maupun "Barang Keluar" sekarang ditarik utuh dari _CameraPreview_ milik Tamu Component, sehingga kini _UI Camera_ untuk memindai barang tampil identik dengan Kamera Wajah Tamu (Ada efek tombol kedip _pulse_, lensa bundar elegan).
- **Validasi No HP Penerima**: Limit panjang di _BarangKeluarScreen_ selaras dengan Tamu yakni 11 hingga 13 digit.

## 26. Memperbaiki Jarak Detail Chip & Urutan List Barang
- Mengubah dimensi _DetailChip_ di dalam _BarangCardStack_ dengan mematenkan kelebaran judul seukuran `60.dp` supaya sejajar rapi secara vertikal sama persis seperti pada _TamuCardStack_.
- Menghapus modifikator `.reversed()` di UI Android (`BarangScreen.kt`) guna merawat keaslian _Sorting_ Raw SQL Backend Python supaya kondisi "_Barang Belum Diambil_ (`tgl_jam_keluar IS NULL`)" secara hierarki mendominasi letaknya di barisan teratas (sesuai Query Asli).

## 27. Fix Next.js Client Request ReferenceError (Flatpickr Types)
- Date: 2026-02-21
- Repos: apppatrol-admin
- **Issue**: Modifying `date-picker.tsx` caused the entire React Component chunk loading to crash natively with `Application error: a client-side exception`. This error specifically triggered off `import Hook = flatpickr.Options.Hook;` rendering logic syntax failing in production minification via SWC. Next.JS cannot execute TS Types natively.
- **Solution**: Explicitly enforced TS type isolation inside `DatePicker` to exclude Types from runtime output. Syntactically replaced `import Hook = flatpickr.Options.Hook;` with explicit types via `type Hook = flatpickr.Options.Hook;` solving React Component errors on build. Restarted the running node instance with PM2.
- **Status**: Implemented, built NextJS codebase without errors and fully operational on `patrol-frontend`.

