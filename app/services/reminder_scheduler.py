"""
Reminder Scheduler
==================
Dijalankan setiap menit oleh APScheduler di startup FastAPI.

Alur:
1. Ambil semua reminder_settings yang is_active=1
2. Untuk setiap reminder, tentukan jam target berdasarkan type
3. Hitung window: jam_target - minutes_before  (±1 menit toleransi)
4. Ambil semua karyawan yang memenuhi kriteria target_role / target_dept / target_cabang
5. Kirim FCM push notification ke device masing-masing
"""

import logging
from datetime import datetime, date, timedelta, time as dtime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.database import SessionLocal
from app.models.models import (
    ReminderSettings, Karyawan, KaryawanDevices, Userkaryawan,
    Presensi, PresensiJamkerja, SetJamKerjaByDate, SetJamKerjaByDay,
    PatrolSchedules
)
from app.core.fcm import _send_to_tokens as fcm_send

logger = logging.getLogger("reminder_scheduler")

HARI_MAP = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis',
            4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}

# Timezone WIB (UTC+7) — server berjalan di UTC, jadwal patroli & absen dalam WIB
TZ_WIB = timezone(timedelta(hours=7))


def _get_patroli_niks(db: Session, kode_dept: str = None, kode_cabang: str = None) -> list:
    """
    Ambil NIK semua karyawan aktif di dept & cabang yang sesuai jadwal patroli.
    Jika kode_dept/kode_cabang NULL (di jadwal), ambil semua karyawan tanpa filter itu.
    """
    query = db.query(Karyawan)
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
    return [k.nik for k in query.all()]


# ─────────────────────────────────────────────────────────────────────────────
# FCM Helper
# ─────────────────────────────────────────────────────────────────────────────
def _send_fcm_to_niks(db: Session, niks: list, title: str, body: str, reminder_type: str, audio_only: bool = False):
    if not niks:
        return

    all_devices = db.query(KaryawanDevices).filter(
        KaryawanDevices.nik.in_(niks),
        KaryawanDevices.fcm_token.isnot(None),
        KaryawanDevices.fcm_token != ""
    ).order_by(KaryawanDevices.id.desc()).all()

    seen_niks = set()
    tokens = []
    for d in all_devices:
        if d.nik not in seen_niks:
            seen_niks.add(d.nik)
            tokens.append(d.fcm_token)


    if not tokens:
        logger.info(f"[Reminder:{reminder_type}] Tidak ada FCM token — skip")
        return

    # Kirim menggunakan fcm.py (force IPv4, tidak hang)
    payload = {
        "type":          "reminder",
        "reminder_type": reminder_type,
        "title":         title,
        "body":          body,
        "audio_only":    "true" if audio_only else "false"
    }
    results = fcm_send(tokens, payload)

    ok  = sum(1 for r in results if r.get("status") == 200)
    err = len(results) - ok
    aud_str = " (AUDIO ONLY)" if audio_only else ""
    logger.info(f"[Reminder:{reminder_type}]{aud_str} Terkirim {ok}/{len(tokens)} device | gagal={err}")


# ─────────────────────────────────────────────────────────────────────────────
# Resolve Jam Kerja aktif untuk satu karyawan hari ini
# ─────────────────────────────────────────────────────────────────────────────
def _get_jam_masuk_pulang(nik: str, db: Session, today: date = None):
    """
    Return (jam_masuk, jam_pulang, is_libur, presensi_obj)
    Hanya menggunakan determine_jam_kerja_hari_ini agar 100% akurat dengan hierarki Absensi.
    """
    from app.routers.absensi_legacy import determine_jam_kerja_hari_ini
    if today is None:
        today = datetime.now(TZ_WIB).date()
        
    now_wib = datetime.now(TZ_WIB)
    
    jam_kerja_obj, presensi = determine_jam_kerja_hari_ini(db, nik, today, now_wib)
    
    if not jam_kerja_obj:
        return None, None, False, presensi, None
        
    is_libur = False
    if jam_kerja_obj.kode_jam_kerja == 'LIBR' or (jam_kerja_obj.nama_jam_kerja and 'Libur' in jam_kerja_obj.nama_jam_kerja):
        is_libur = True
        
    return jam_kerja_obj.jam_masuk, jam_kerja_obj.jam_pulang, is_libur, presensi, jam_kerja_obj.kode_jam_kerja


# ─────────────────────────────────────────────────────────────────────────────
# Ambil karyawan yang memenuhi filter reminder
# ─────────────────────────────────────────────────────────────────────────────
def _get_target_karyawan(db: Session, setting: ReminderSettings) -> list:
    """
    Kembalikan list NIK karyawan yang sesuai target_role / target_dept / target_cabang.
    Gunakan role via query raw ke model_has_roles + roles.
    """
    from sqlalchemy import text as sqltxt
    query = db.query(Karyawan)

    if setting.target_dept:
        query = query.filter(Karyawan.kode_dept == setting.target_dept)
    if setting.target_cabang:
        query = query.filter(Karyawan.kode_cabang == setting.target_cabang)

    if setting.target_role:
        # Join via raw SQL ke tabel roles
        niks_with_role = db.execute(sqltxt("""
            SELECT uk.nik
            FROM users_karyawan uk
            JOIN model_has_roles mhr ON uk.id_user = mhr.model_id
            JOIN roles r ON mhr.role_id = r.id
            WHERE mhr.model_type = 'App\\\\Models\\\\User'
              AND r.name LIKE :role_pattern
        """), {"role_pattern": f"%{setting.target_role}%"}).fetchall()
        nik_list = [r[0] for r in niks_with_role]
        if not nik_list:
            return []
        query = query.filter(Karyawan.nik.in_(nik_list))

    return [k.nik for k in query.all()]


# ─────────────────────────────────────────────────────────────────────────────
# Cek apakah waktu sekarang dalam window target
# ─────────────────────────────────────────────────────────────────────────────
def _in_window(now: datetime, target_time: dtime, minutes_before: int) -> bool:
    """
    Apakah now berada dalam [target - minutes_before - 1, target - minutes_before + 1]?
    Toleransi ±1 menit untuk menghindari miss saat scheduler terlambat.
    """
    target_dt  = datetime.combine(now.date(), target_time) - timedelta(minutes=minutes_before)
    window_start = target_dt - timedelta(minutes=1)
    window_end   = target_dt + timedelta(minutes=1)
    return window_start <= now <= window_end


# ─────────────────────────────────────────────────────────────────────────────
def _is_active_patrol_window_and_due(now: datetime, sch_start: dtime, sch_end: dtime, minutes_before: int):
    """
    Untuk patroli: 
    1. Ping H-minutes_before (seperti biasa) -> Full Notif (return True, False)
    2. Jika sudah masuk jam window (start <= now <= end), ping setiap kelipatan 5 menit -> Audio Only (return True, True)
    Kembalian: (should_ping, audio_only)
    """
    now_time = now.time()
    today_date = now.date()
    
    # 1. Cek H-minus (sama dengan _in_window standard)
    target_dt  = datetime.combine(today_date, sch_start) - timedelta(minutes=minutes_before)
    window_start = target_dt - timedelta(minutes=1)
    window_end   = target_dt + timedelta(minutes=1)
    if window_start <= now <= window_end:
        return True, False
        
    # 2. Cek apakah sedang berada di DALAM window patroli
    # Helper untuk logic melampaui tengah malam
    start_dt = datetime.combine(today_date, sch_start)
    end_dt = datetime.combine(today_date, sch_end)
    if end_dt <= start_dt:
        # Jika jadwal seperti 23:00 - 05:00
        if now_time >= sch_start:
            end_dt += timedelta(days=1)
        else: # now_time < sch_end
            start_dt -= timedelta(days=1)
            
    if start_dt <= now < end_dt:
        # Ping berulang setiap 5 menit pas (0, 5, 10, ... 55) (AUDIO ONLY)
        if now.minute % 5 == 0:
            return True, True
            
    return False, False

# ─────────────────────────────────────────────────────────────────────────────
# Main scheduler job
# ─────────────────────────────────────────────────────────────────────────────
def run_reminder_check():
    db: Session = SessionLocal()
    try:
        now_wib = datetime.now(TZ_WIB)          # waktu sekarang dalam WIB
        now     = now_wib.replace(tzinfo=None)   # naive untuk perbandingan
        today   = now.date()
        logger.info(f"[Reminder] Scheduler tick (WIB): {now.strftime('%H:%M:%S')} | UTC: {datetime.utcnow().strftime('%H:%M:%S')}")

        settings = db.query(ReminderSettings).filter(ReminderSettings.is_active == 1).all()

        for setting in settings:
            try:
                niks = _get_target_karyawan(db, setting)
                if not niks:
                    continue

                fire_niks = []  # NIK yang akan dikirimi reminder

                # ─── absen_masuk ───────────────────────────────────────────
                if setting.type == 'absen_masuk':
                    for nik in niks:
                        jam_masuk, _, is_libur, presensi, _ = _get_jam_masuk_pulang(nik, db, today)
                        if jam_masuk and not is_libur and _in_window(now, jam_masuk, setting.minutes_before):
                            # Jika belum ada tap In 
                            if not presensi or presensi.jam_in is None:
                                fire_niks.append(nik)

                # ─── absen_pulang ──────────────────────────────────────────
                elif setting.type == 'absen_pulang':
                    for nik in niks:
                        _, jam_pulang, is_libur, presensi, _ = _get_jam_masuk_pulang(nik, db, today)
                        if jam_pulang and not is_libur and _in_window(now, jam_pulang, setting.minutes_before):
                            # Sudah absen masuk tapi belum absen pulang
                            if presensi and presensi.jam_in is not None and presensi.jam_out is None:
                                fire_niks.append(nik)

                # ─── absen_patroli ─────────────────────────────────────────
                elif setting.type == 'absen_patroli':
                    from app.models.models import PatrolSessions
                    patrol_schedules = db.query(PatrolSchedules).filter(
                        PatrolSchedules.is_active == True
                    ).all()

                    # Optimize Karyawan lookups
                    karyawan_dict = {k.nik: k for k in db.query(Karyawan).filter(Karyawan.nik.in_(niks)).all()}
                    group_niks_cache = {}
                    
                    audio_niks = []

                    for sch in patrol_schedules:
                        if setting.target_shift and sch.kode_jam_kerja != setting.target_shift:
                            continue

                        should_ping, is_audio_only = _is_active_patrol_window_and_due(now, sch.start_time, sch.end_time, setting.minutes_before)
                        if not should_ping:
                            continue

                        # Check each targeted NIK
                        for nik in niks:
                            kary = karyawan_dict.get(nik)
                            if not kary: continue

                            # 1. Pastikan jadwal ini relevan untuk Cabang & Dept karyawan
                            if sch.kode_cabang and sch.kode_cabang != kary.kode_cabang:
                                continue
                            if sch.kode_dept and sch.kode_dept != kary.kode_dept:
                                continue
                                
                            # 2. Pastikan jadwal kerja Karyawan sesuai dengan jadwal Patroli
                            _, _, is_libur, presensi, kode_jk = _get_jam_masuk_pulang(nik, db, today)
                            if is_libur or not kode_jk:
                                continue
                                
                            if sch.kode_jam_kerja and sch.kode_jam_kerja != kode_jk:
                                continue
                                
                            # SYARAT MUTLAK 1: Karyawan harus sudah hadir (Absen Masuk) hari ini.
                            if not presensi or presensi.jam_in is None:
                                continue
                                    
                            # SYARAT MUTLAK 2: Jika jam sekarang sudah di luar shift/jam pulang kerja aslinya, skip (misal ybs lupa absen pulang)
                            jam_pulang = presensi.jam_out
                            if not jam_pulang: # Lupa absen pulang
                                _, jam_pulang_asli, _, _, _ = _get_jam_masuk_pulang(nik, db, today)
                                if jam_pulang_asli:
                                    # Hitung rentang sebenarnya
                                    pulang_dt = datetime.combine(today, jam_pulang_asli).replace(tzinfo=TZ_WIB).replace(tzinfo=None)
                                    jam_masuk_asli = jam_kerja_obj.jam_masuk if 'jam_kerja_obj' in locals() else None # fallback aman
                                    # Jika jam malam
                                    if hasattr(presensi, 'jam_masuk') and presensi.jam_masuk and jam_pulang_asli < presensi.jam_masuk:
                                        pulang_dt += timedelta(days=1)
                                    # Bandingkan jika sudah lewat dari batas kepulangan
                                    if now > pulang_dt:
                                        continue

                            # 3. Cek apakah di rentang jadwal Patroli ini sesi karyawan (atau rekan cabangnya) sudah done
                            # Window Schedule:
                            start_dt = datetime.combine(today, sch.start_time)
                            end_dt = datetime.combine(today, sch.end_time)
                            if end_dt <= start_dt:
                                end_dt += timedelta(days=1)
                                
                            cache_key = f"{kary.kode_cabang}_{kary.kode_dept}"
                            if cache_key not in group_niks_cache:
                                group_niks_cache[cache_key] = [
                                    r[0] for r in db.query(Karyawan.nik).filter(
                                        Karyawan.kode_cabang == kary.kode_cabang,
                                        Karyawan.kode_dept   == kary.kode_dept
                                    ).all()
                                ]
                                
                            group_niks = group_niks_cache[cache_key]
                                
                            # Cari PatrolSession yang beririsan
                            sudah_patroli = db.query(PatrolSessions).filter(
                                PatrolSessions.nik.in_(group_niks),
                                PatrolSessions.created_at >= start_dt,
                                PatrolSessions.created_at <= end_dt
                            ).first()

                            if not sudah_patroli:
                                if is_audio_only:
                                    audio_niks.append(nik)
                                else:
                                    fire_niks.append(nik)

                    fire_niks = list(set(fire_niks))
                    
                    # Buang nik di audio yang sudah ada di fire_niks (kembar)
                    audio_niks = list(set(audio_niks) - set(fire_niks))
                    
                    if audio_niks:
                        _send_fcm_to_niks(
                            db=db,
                            niks=audio_niks,
                            title=setting.label,
                            body=setting.message,
                            reminder_type=setting.type,
                            audio_only=True
                        )

                # ─── cleaning_task / driver_task ───────────────────────────
                elif setting.type in ('cleaning_task', 'driver_task'):
                    # Reminder di jam masuk kerja masing-masing
                    for nik in niks:
                        jam_masuk, _, is_libur, _, _ = _get_jam_masuk_pulang(nik, db, today)
                        if jam_masuk and not is_libur and _in_window(now, jam_masuk, setting.minutes_before):
                            fire_niks.append(nik)

                if fire_niks:
                    _send_fcm_to_niks(
                        db=db,
                        niks=fire_niks,
                        title=setting.label,
                        body=setting.message,
                        reminder_type=setting.type
                    )

            except Exception as ex:
                logger.error(f"[Reminder] Error processing setting id={setting.id}: {ex}")

    except Exception as e:
        logger.error(f"[Reminder] Scheduler error: {e}")
    finally:
        db.close()
