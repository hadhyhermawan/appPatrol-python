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
def _send_fcm_to_niks(db: Session, niks: list, title: str, body: str, reminder_type: str):
    if not niks:
        return

    # Ambil 1 token terbaru per NIK
    latest_subq = db.query(
        KaryawanDevices.nik,
        func.max(KaryawanDevices.updated_at).label('max_updated')
    ).filter(KaryawanDevices.nik.in_(niks)).group_by(KaryawanDevices.nik).subquery()

    devices = db.query(KaryawanDevices).join(
        latest_subq,
        (KaryawanDevices.nik == latest_subq.c.nik) &
        (KaryawanDevices.updated_at == latest_subq.c.max_updated)
    ).all()

    tokens = [d.fcm_token for d in devices if d.fcm_token]
    if not tokens:
        logger.info(f"[Reminder:{reminder_type}] Tidak ada FCM token — skip")
        return

    # Kirim menggunakan fcm.py (force IPv4, tidak hang)
    results = fcm_send(tokens, {
        "type":          "reminder",
        "reminder_type": reminder_type,
        "title":         title,
        "body":          body,
    })

    ok  = sum(1 for r in results if r.get("status") == 200)
    err = len(results) - ok
    logger.info(f"[Reminder:{reminder_type}] Terkirim {ok}/{len(tokens)} device | gagal={err}")


# ─────────────────────────────────────────────────────────────────────────────
# Resolve Jam Kerja aktif untuk satu karyawan hari ini
# ─────────────────────────────────────────────────────────────────────────────
def _get_jam_masuk_pulang(nik: str, db: Session, today: date = None):
    """
    Return (jam_masuk, jam_pulang) as time objects, or (None, None).
    Pakai today dalam WIB. Jika karyawan shift malam lintas hari (presensi kemarin),
    return jam kerja dari tanggal kemarin.
    """
    if today is None:
        today = datetime.now(TZ_WIB).date()
    yesterday = today - timedelta(days=1)
    hari = HARI_MAP[today.weekday()]

    # 0. Cek presensi aktif: hari ini atau kemarin (lintas hari)
    for tgl in [today, yesterday]:
        presensi = db.query(Presensi).filter(
            Presensi.nik == nik,
            Presensi.tanggal == tgl,
            Presensi.jam_in != None
        ).first()
        if presensi and presensi.kode_jam_kerja:
            jk = db.query(PresensiJamkerja).filter(
                PresensiJamkerja.kode_jam_kerja == presensi.kode_jam_kerja
            ).first()
            if jk:
                return jk.jam_masuk, jk.jam_pulang

    # 1. By Date (hari ini)
    jk_date = db.query(SetJamKerjaByDate).filter(
        SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today
    ).first()
    if jk_date:
        jk = db.query(PresensiJamkerja).filter(
            PresensiJamkerja.kode_jam_kerja == jk_date.kode_jam_kerja
        ).first()
        if jk:
            return jk.jam_masuk, jk.jam_pulang

    # 2. By Day
    jk_day = db.query(SetJamKerjaByDay).filter(
        SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == hari
    ).first()
    if jk_day:
        jk = db.query(PresensiJamkerja).filter(
            PresensiJamkerja.kode_jam_kerja == jk_day.kode_jam_kerja
        ).first()
        if jk:
            return jk.jam_masuk, jk.jam_pulang

    # 3. Default dari master karyawan
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if karyawan and karyawan.kode_jadwal:
        jk = db.query(PresensiJamkerja).filter(
            PresensiJamkerja.kode_jam_kerja == karyawan.kode_jadwal
        ).first()
        if jk:
            return jk.jam_masuk, jk.jam_pulang

    return None, None


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
                        jam_masuk, _ = _get_jam_masuk_pulang(nik, db, today)
                        if jam_masuk and _in_window(now, jam_masuk, setting.minutes_before):
                            # Belum absen masuk hari ini maupun kemarin (lintas hari)
                            yesterday = today - timedelta(days=1)
                            sudah = db.query(Presensi).filter(
                                Presensi.nik == nik,
                                Presensi.tanggal.in_([today, yesterday]),
                                Presensi.jam_in != None
                            ).first()
                            if not sudah:
                                fire_niks.append(nik)

                # ─── absen_pulang ──────────────────────────────────────────
                elif setting.type == 'absen_pulang':
                    for nik in niks:
                        _, jam_pulang = _get_jam_masuk_pulang(nik, db, today)
                        if jam_pulang and _in_window(now, jam_pulang, setting.minutes_before):
                            # Sudah absen masuk tapi belum absen pulang
                            # Handle lintas hari: cek hari ini atau kemarin
                            yesterday = today - timedelta(days=1)
                            presensi = db.query(Presensi).filter(
                                Presensi.nik == nik,
                                Presensi.tanggal.in_([today, yesterday]),
                                Presensi.jam_in != None,
                                Presensi.jam_out == None
                            ).first()
                            if presensi:
                                fire_niks.append(nik)

                # ─── absen_patroli ─────────────────────────────────────────
                elif setting.type == 'absen_patroli':
                    patrol_schedules = db.query(PatrolSchedules).filter(
                        PatrolSchedules.is_active == True
                    ).all()

                    for sch in patrol_schedules:
                        # Filter by shift jika diset di reminder
                        if setting.target_shift and sch.kode_jam_kerja != setting.target_shift:
                            continue

                        if not _in_window(now, sch.start_time, setting.minutes_before):
                            continue

                        # Ambil NIK semua karyawan di dept & cabang jadwal patroli
                        patroli_niks = _get_patroli_niks(
                            db,
                            kode_dept=sch.kode_dept,
                            kode_cabang=sch.kode_cabang
                        )

                        logger.info(
                            f"[Reminder:absen_patroli] Jadwal '{sch.name}' jam {sch.start_time} "
                            f"shift={sch.kode_jam_kerja} dept={sch.kode_dept} cabang={sch.kode_cabang} "
                            f"→ {len(patroli_niks)} karyawan"
                        )
                        fire_niks.extend(patroli_niks)

                    fire_niks = list(set(fire_niks))

                # ─── cleaning_task / driver_task ───────────────────────────
                elif setting.type in ('cleaning_task', 'driver_task'):
                    # Reminder di jam masuk kerja masing-masing
                    for nik in niks:
                        jam_masuk, _ = _get_jam_masuk_pulang(nik, db)
                        if jam_masuk and _in_window(now, jam_masuk, setting.minutes_before):
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
