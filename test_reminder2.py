from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import ReminderSettings, PatrolSchedules, Karyawan, PatrolSessions, KaryawanDevices, Presensi
from app.services.reminder_scheduler import _get_target_karyawan, _in_window, _get_jam_masuk_pulang, _is_active_patrol_window_and_due
from datetime import datetime, timedelta, time
import pytz

TZ_WIB = pytz.timezone('Asia/Jakarta')

db = SessionLocal()
now_wib = datetime.now(TZ_WIB)
now = now_wib.replace(tzinfo=None)
today = now.date()

settings = db.query(ReminderSettings).filter(ReminderSettings.is_active == 1, ReminderSettings.type == 'absen_patroli').all()

for setting in settings:
    niks = _get_target_karyawan(db, setting)
    print(f"Setting: {setting.label}, Type: {setting.type}, NIKs matched by target_role '{setting.target_role}': {len(niks)}")
    
    if len(niks) > 0:
        patrol_schedules = db.query(PatrolSchedules).filter(PatrolSchedules.is_active == True).all()

        for sch in patrol_schedules:
            if setting.target_shift and sch.kode_jam_kerja != setting.target_shift:
                continue

            # Bypass real time, check with an arbitrary active window:
            check_now = datetime.combine(now.date(), time(20, 20)) # Check 20:20 (for schedule 20:00 - 21:00)
            should_ping, is_audio_only = _is_active_patrol_window_and_due(check_now, sch.start_time, sch.end_time, setting.minutes_before)
            
            if should_ping:
                print(f"Schedule: {sch.start_time} - {sch.end_time} MATCHES! audio={is_audio_only}")

db.close()
