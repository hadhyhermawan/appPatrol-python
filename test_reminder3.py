from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.models import ReminderSettings, PatrolSchedules, Karyawan, PatrolSessions, KaryawanDevices, Presensi
from app.services.reminder_scheduler import _get_target_karyawan, _get_jam_masuk_pulang, _is_active_patrol_window_and_due
from datetime import datetime, timedelta, time
import pytz

TZ_WIB = pytz.timezone('Asia/Jakarta')

def evaluate_nik(db: Session, setting: ReminderSettings, nik_to_test: str, check_time: datetime, today: datetime.date):
    print(f"\n--- Menguji NIK: {nik_to_test} pada pukul {check_time.time()} ---")
    
    kary_test = db.query(Karyawan).filter(Karyawan.nik == nik_to_test).first()
    if not kary_test: return

    print(f"Cabang: {kary_test.kode_cabang}, Dept: {kary_test.kode_dept}")
    _, _, is_libur, presensi, kode_jk = _get_jam_masuk_pulang(nik_to_test, db, today)
    print(f"Jam Kerja: {kode_jk}, Libur: {is_libur}, Presensi Masuk: {presensi.jam_in if presensi else 'Belum Absen'}")
    
    if is_libur or not kode_jk: return
    if not presensi or presensi.jam_in is None: return

    patrol_schedules = db.query(PatrolSchedules).filter(PatrolSchedules.is_active == True).all()
    
    for sch in patrol_schedules:
        should_ping, is_audio_only = _is_active_patrol_window_and_due(check_time, sch.start_time, sch.end_time, setting.minutes_before)
        if not should_ping:
            continue
            
        print(f"  [Match] JDwl {sch.start_time}-{sch.end_time} ping={should_ping}, audio_only={is_audio_only} Cabang={sch.kode_cabang} Dept={sch.kode_dept} JK={sch.kode_jam_kerja}")

        if setting.target_shift and sch.kode_jam_kerja != setting.target_shift: continue
        if sch.kode_cabang and sch.kode_cabang != kary_test.kode_cabang: continue
        if sch.kode_dept and sch.kode_dept != kary_test.kode_dept: continue
        if sch.kode_jam_kerja and sch.kode_jam_kerja != kode_jk: continue

        start_dt = datetime.combine(today, sch.start_time)
        end_dt = datetime.combine(today, sch.end_time)
        if end_dt <= start_dt: end_dt += timedelta(days=1)
        
        group_niks = [
            r[0] for r in db.query(Karyawan.nik).filter(
                Karyawan.kode_cabang == kary_test.kode_cabang,
                Karyawan.kode_dept   == kary_test.kode_dept
            ).all()
        ]

        sudah_patroli = db.query(PatrolSessions).filter(
            PatrolSessions.nik.in_(group_niks),
            PatrolSessions.created_at >= start_dt,
            PatrolSessions.created_at <= end_dt
        ).first()
        
        if sudah_patroli:
           print(f"    -> SUDAH PATROLI. NIK={sudah_patroli.nik}")
        else:
           print(f"    -> BELUM PATROLI! Boleh Tembak Notifikasi! Audio Only: {is_audio_only}")

if __name__ == '__main__':
    db = SessionLocal()
    now_wib = datetime.now(TZ_WIB)
    today = now_wib.date()
    
    settings = db.query(ReminderSettings).filter(ReminderSettings.is_active == 1, ReminderSettings.type == 'absen_patroli').all()
    
    # 22.54 simulation
    check_time = datetime.combine(today, time(22, 54, 0))
    for setting in settings:
        evaluate_nik(db, setting, "1801042008930002", check_time, today)
        evaluate_nik(db, setting, "1801042008930003", check_time, today)
        
    db.close()
