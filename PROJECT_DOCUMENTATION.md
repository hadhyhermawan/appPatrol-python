
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
