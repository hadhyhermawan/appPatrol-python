
## 21. Fix Absensi Fallback (NON SHIFT)
- Date: 2026-02-21
- Repo: appPatrol-python
- **Issue**: Karyawan with `lock_jam_kerja = 0` (allowed to change their shift) would send `kode_jam_kerja: null` from the Android app when performing `absen`. The Python backend `POST /api/android/absensi/absen` would default this to `"NS"` and immediately fallback to the first row in `presensi_jamkerja` (which happens to be `0001 - NON SHIFT`), completely ignoring their actual shift schedule on that day.
- **Solution**: Refactored the `get_presensi_hari_ini` scheduling logic into an independent and reusable function `determine_jam_kerja_hari_ini()`. Now, if the frontend sends a `null` or `'NS'` shift, the `absen` endpoint uses this function to calculate the mathematically correct shift for the day (checking `by_date_extra` -> `by_date` -> `by_day` -> `dept` -> `user_default`), ensuring users are accurately recorded according to their schedule (e.g. `0003 - SF SORE`) instead of falsely marked as `NON SHIFT`.
- **Status**: Tested and pushed to remote. Service restarted.

