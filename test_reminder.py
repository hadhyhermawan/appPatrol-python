from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import ReminderSettings, PatrolSchedules, Karyawan
from app.services.reminder_scheduler import _get_target_karyawan, _in_window, _get_jam_masuk_pulang, _is_active_patrol_window_and_due
from datetime import datetime, timedelta, time
import pytz

TZ_WIB = pytz.timezone('Asia/Jakarta')

db = SessionLocal()
now_wib = datetime.now(TZ_WIB)
now = now_wib.replace(tzinfo=None)

settings = db.query(ReminderSettings).filter(ReminderSettings.is_active == 1).all()

for setting in settings:
    niks = _get_target_karyawan(db, setting)
    print(f"Setting: {setting.type}, Label: {setting.label}, TargetRole: {setting.target_role}, NIKs found: {len(niks)}")
    if setting.type == 'absen_patroli':
        print(f"  Target Shift: {setting.target_shift}, MinsBefore: {setting.minutes_before}")
        patrol_schedules = db.query(PatrolSchedules).filter(PatrolSchedules.is_active == True).all()

        for sch in patrol_schedules:
            if setting.target_shift and sch.kode_jam_kerja != setting.target_shift:
                continue
            should_ping, is_audio_only = _is_active_patrol_window_and_due(now, sch.start_time, sch.end_time, setting.minutes_before)
            
            print(f"  Schedule {sch.id} ({sch.start_time} - {sch.end_time}): should_ping={should_ping}, is_audio_only={is_audio_only}")
            
db.close()
