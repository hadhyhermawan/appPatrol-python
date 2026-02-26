from sqlalchemy.orm import Session
from sqlalchemy import desc, extract
from datetime import datetime, date, timedelta
from app.models.models import (
    Presensi, PresensiJamkerja, Karyawan,
    SetJamKerjaByDate, SetJamKerjaByDay,
    PresensiJamkerjaBydept, PresensiJamkerjaBydateExtra
)

def determine_jam_kerja_hari_ini(db: Session, nik: str, today: date, now_wib: datetime):
    # Dynamic import to avoid circular dependency
    from app.models.models import PresensiJamkerjaByDeptDetail
    
    jam_kerja_obj = None
    presensi = None
    
    # Check if there is an active ongoing shift
    presensi_aktif = db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today, Presensi.jam_out == None).first()
    
    # Logic Lintas Hari: Check if yesterday's shift is still ongoing
    if not presensi_aktif:
        yesterday = today - timedelta(days=1)
        presensi_yesterday = db.query(Presensi).filter(
            Presensi.nik == nik, 
            Presensi.tanggal == yesterday,
            Presensi.lintashari == 1,
            Presensi.jam_out == None
        ).first()
        if presensi_yesterday:
            presensi_aktif = presensi_yesterday

    # If there is an active shift, lock onto it
    if presensi_aktif:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == presensi_aktif.kode_jam_kerja).first(), presensi_aktif

    # We don't have an active shift. Let's find the best schedule.
    
    # Contexts to prevent falling back incorrectly:
    has_roster_this_month = db.query(SetJamKerjaByDate).filter(
        SetJamKerjaByDate.nik == nik,
        extract('month', SetJamKerjaByDate.tanggal) == today.month,
        extract('year', SetJamKerjaByDate.tanggal) == today.year
    ).count() > 0

    has_regular_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik).count() > 0

    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    has_dept_day = False
    dept_header = None
    if karyawan and karyawan.kode_dept:
        dept_header = db.query(PresensiJamkerjaBydept).filter(
            PresensiJamkerjaBydept.kode_dept == karyawan.kode_dept,
            PresensiJamkerjaBydept.kode_cabang == karyawan.kode_cabang
        ).first()
        if dept_header:
            has_dept_day = db.query(PresensiJamkerjaByDeptDetail).filter(
                PresensiJamkerjaByDeptDetail.kode_jk_dept == dept_header.kode_jk_dept
            ).count() > 0

    days_map = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    day_name = days_map[now_wib.weekday()]

    # Gather all potential schedules for today in order of priority:
    # 0. Extra Date
    # 1. Roster Date
    # 2. Regular Day
    # 3. Dept Day
    # 4. Fallback Kode Jadwal
    
    # Let's collect ALL valid uncompleted shifts, or if all completed, return the primary completed one.
    
    possible_shifts = []
    
    # Priority 0: Extra Date
    extra_dates = db.query(PresensiJamkerjaBydateExtra).filter(PresensiJamkerjaBydateExtra.nik == nik, PresensiJamkerjaBydateExtra.tanggal == today).order_by(desc(PresensiJamkerjaBydateExtra.id)).all()
    for ex in extra_dates:
        possible_shifts.append({'kode': ex.kode_jam_kerja, 'source': 'extra'})

    # Priority 1: Roster
    if not has_roster_this_month:
        # Fallback to Priority 2: Regular Day
        if not has_regular_day:
            # Fallback to Priority 3: Dept Day
            if not has_dept_day:
                # Priority 4: Karyawan Default
                if karyawan and karyawan.kode_jadwal:
                    possible_shifts.append({'kode': karyawan.kode_jadwal, 'source': 'default'})
            else:
                # Get Dept today
                dept_detail = db.query(PresensiJamkerjaByDeptDetail).filter(
                    PresensiJamkerjaByDeptDetail.kode_jk_dept == dept_header.kode_jk_dept,
                    PresensiJamkerjaByDeptDetail.hari == day_name
                ).first()
                if dept_detail and dept_detail.kode_jam_kerja:
                    possible_shifts.append({'kode': dept_detail.kode_jam_kerja, 'source': 'dept'})
        else:
            # Get Regular today
            by_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == day_name).first()
            if by_day:
                 possible_shifts.append({'kode': by_day.kode_jam_kerja, 'source': 'byday'})
    else:
        # User is on roster this month.
        by_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today).first()
        if by_date:
            possible_shifts.append({'kode': by_date.kode_jam_kerja, 'source': 'roster'})

    # Now, find the first schedule they HAVE NOT FINISHED
    finished_presensis = []
    
    for s in possible_shifts:
        kode = s['kode']
        
        # Check if they finished this one
        finished_p = db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today, Presensi.kode_jam_kerja == kode, Presensi.jam_out != None).first()
        if not finished_p:
            # Found one!
            jk = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == kode).first()
            if jk:
                return jk, None
        else:
            finished_presensis.append((kode, finished_p))
            
    # If we get here, they EITHER finished all their shifts today OR they don't have any shifts today.
    # If they finished a shift, we usually return the ONE they finished so the UI says "Abse Pulang Selesai" instead of "Tidak ada jadwal"
    if finished_presensis:
        # Return the primary/base one as the visual anchor. If multiple, return the last one they did.
        # But honestly, returning the last finished one is fine.
        last_kode, last_p = finished_presensis[-1]
        jk = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == last_kode).first()
        return jk, last_p
        
    return None, None
    
