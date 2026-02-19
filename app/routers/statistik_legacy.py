from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from datetime import date, datetime, timedelta
from typing import Optional
from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import (
    Users, Karyawan, Userkaryawan, Presensi, PresensiJamkerja, 
    PatrolSessions, PatrolSchedules, Jabatan, Departemen, Cabang
)
import calendar

router = APIRouter(
    prefix="/api/android/statistik",
    tags=["Statistik Legacy"],
)

@router.get("/kinerja")
async def get_kinerja(
    tipe_laporan: str = Query("bulanan", enum=["harian", "bulanan"]),
    bulan: Optional[str] = Query(None),
    tahun: Optional[str] = Query(None),
    tanggal_dari: Optional[str] = Query(None),
    tanggal_sampai: Optional[str] = Query(None),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Validate User & Karyawan
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == user.id).first()
    if not user_karyawan:
        raise HTTPException(status_code=404, detail="Relasi user-karyawan tidak ditemukan")

    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    if not karyawan:
        raise HTTPException(status_code=404, detail="Data karyawan detail tidak ditemukan")

    # Fetch details for response
    jabatan_nama = karyawan.jabatan.nama_jabatan if karyawan.jabatan else "-"
    dept_nama = karyawan.departemen.nama_dept if karyawan.departemen else "-"
    cabang_nama = "Unknown"
    
    # Manually fetch Cabang if relationship not straightforward or to match PHP explicit join
    if karyawan.kode_cabang:
        cabang = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
        if cabang: cabang_nama = cabang.nama_cabang

    # 2. Group NIKs (Same Cabang & Dept)
    group_niks = db.query(Karyawan.nik).filter(
        Karyawan.kode_cabang == karyawan.kode_cabang,
        Karyawan.kode_dept == karyawan.kode_dept
    ).all()
    group_niks_list = [n[0] for n in group_niks]

    # 3. Determine Date Range
    today = date.today()
    if tipe_laporan == 'harian':
        start_date_str = tanggal_dari if tanggal_dari else str(today)
        end_date_str = tanggal_sampai if tanggal_sampai else start_date_str
    else:
        # Bulanan
        m = int(bulan) if bulan else today.month
        y = int(tahun) if tahun else today.year
        _, last_day = calendar.monthrange(y, m)
        start_date_str = f"{y}-{m:02d}-01"
        end_date_str = f"{y}-{m:02d}-{last_day}"

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()

    # 4. Attendance Summary
    # PHP: leftJoin presensi_jamkerja
    # Select count status
    
    summary_query = db.query(
        func.count(func.distinct(Presensi.tanggal)).label("total_hari"),
        func.coalesce(func.sum(PresensiJamkerja.total_jam), 0).label("total_jam"),
        func.sum(func.if_(Presensi.status == 'h', 1, 0)).label("hadir"),
        func.sum(func.if_(Presensi.status == 'i', 1, 0)).label("izin"),
        func.sum(func.if_(Presensi.status == 's', 1, 0)).label("sakit"),
        func.sum(func.if_(Presensi.status == 'c', 1, 0)).label("cuti"),
        func.sum(func.if_(Presensi.status == 'a', 1, 0)).label("alfa")
    ).outerjoin(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
     .filter(Presensi.nik == karyawan.nik)\
     .filter(Presensi.tanggal >= start_date, Presensi.tanggal <= end_date)
    
    summary = summary_query.first()
    
    total_hari = int(summary.total_hari or 0)
    total_jam = float(summary.total_jam or 0)
    hadir = int(summary.hadir or 0)
    izin = int(summary.izin or 0)
    sakit = int(summary.sakit or 0)
    cuti = int(summary.cuti or 0)
    alfa = int(summary.alfa or 0)

    # 5. Individual Patrols (Completed)
    patroli_individu = db.query(func.count(PatrolSessions.id))\
        .filter(PatrolSessions.nik == karyawan.nik)\
        .filter(PatrolSessions.status == 'complete')\
        .filter(PatrolSessions.tanggal >= start_date, PatrolSessions.tanggal <= end_date)\
        .scalar() or 0

    # 6. Target & Group Realisation (Complex Logic)
    target_patroli = 0
    patroli_group = 0
    
    try:
        # A. Get User's Presensi (Shift Info) for the range
        presensi_list = db.query(Presensi.tanggal, Presensi.kode_jam_kerja, PresensiJamkerja.jam_masuk, PresensiJamkerja.lintashari)\
            .join(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .filter(Presensi.nik == karyawan.nik)\
            .filter(Presensi.status == 'h')\
            .filter(Presensi.tanggal >= start_date, Presensi.tanggal <= end_date)\
            .all()
            
        presensi_map = {p.tanggal: p for p in presensi_list} # Key: date object
        
        # B. Get All Relevant Schedules
        # Active schedules for this branch/dept or null (global)
        schedules = db.query(PatrolSchedules)\
            .filter(PatrolSchedules.is_active == True)\
            .filter(or_(PatrolSchedules.kode_cabang == None, PatrolSchedules.kode_cabang == karyawan.kode_cabang))\
            .filter(or_(PatrolSchedules.kode_dept == None, PatrolSchedules.kode_dept == karyawan.kode_dept))\
            .all()
            
        # Group schedules by kode_jam_kerja
        schedules_map = {}
        for s in schedules:
            if s.kode_jam_kerja not in schedules_map:
                schedules_map[s.kode_jam_kerja] = []
            schedules_map[s.kode_jam_kerja].append(s)
            
        # C. Get All Group Sessions (Complete) in Range (plus buffer)
        buffer_start = start_date - timedelta(days=1)
        buffer_end = end_date + timedelta(days=1)
        
        group_sessions = db.query(PatrolSessions.tanggal, PatrolSessions.jam_patrol)\
            .filter(PatrolSessions.nik.in_(group_niks_list))\
            .filter(PatrolSessions.status == 'complete')\
            .filter(PatrolSessions.tanggal >= buffer_start, PatrolSessions.tanggal <= buffer_end)\
            .all()
            
        # Convert session times to datetime objects for easy comparison
        session_datetimes = []
        for gs in group_sessions:
            # Combine separate date and time fields
            # Assuming jam_patrol is time or string HH:MM:SS
            # Database model says jam_patrol is Time/String.
            # Convert to full datetime
            dt_str = f"{gs.tanggal} {gs.jam_patrol}" 
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                session_datetimes.append(dt)
            except:
                pass # Skip invalid

        # D. Iterate days
        curr_date = start_date
        while curr_date <= end_date:
            curr_date_str = str(curr_date)
            
            # Find presensi for this day
            presensi_data = next((p for p in presensi_list if str(p.tanggal) == curr_date_str), None)
            
            if presensi_data:
                p_kode_jk = presensi_data.kode_jam_kerja
                
                if p_kode_jk in schedules_map:
                    daily_schedules = schedules_map[p_kode_jk]
                   
                    # Convert shift start time once
                    try:
                        shift_jam_masuk_str = str(presensi_data.jam_masuk) # "HH:MM:SS"
                        shift_start_hour = int(shift_jam_masuk_str.split(':')[0])
                        shift_start_min = int(shift_jam_masuk_str.split(':')[1])
                        
                        is_lintas_hari = False
                        if hasattr(presensi_data, 'lintashari'):
                            # Can be 1, '1', True
                            is_lintas_hari = str(presensi_data.lintashari) == '1'
                            
                        for sched in daily_schedules:
                            target_patroli += 1
                            
                            # Parse Schedule Start & End
                            sched_start_str = str(sched.start_time)
                            sched_end_str = str(sched.end_time)
                            
                            s_start_hour = int(sched_start_str.split(':')[0])
                            s_start_min = int(sched_start_str.split(':')[1])
                            
                            s_end_hour = int(sched_end_str.split(':')[0])
                            
                            # Base Start DateTime = Curr Date + Sched Time
                            s_start_dt = datetime(curr_date.year, curr_date.month, curr_date.day, s_start_hour, s_start_min)
                            
                            # Correction for Lintas Hari Shift
                            # If shift is lintas hari (e.g. 20:00 - 08:00) AND sched start < shift start (e.g. 02:00)
                            # Then this schedule belongs to the NEXT day relative to shift start date
                            # (But shift date in DB is usually the start date)
                            
                            # PHP Logic: if ($jamKerja->lintashari && $schedStartVal->lt($shiftStartVal)) $startDate->addDay();
                            # Compare Time Objects Only
                            sched_time_obj = s_start_dt.time()
                            shift_time_obj = datetime.strptime(shift_jam_masuk_str, "%H:%M:%S").time()
                            
                            if is_lintas_hari and sched_time_obj < shift_time_obj:
                                s_start_dt += timedelta(days=1)
                            
                            # Calculate End DateTime
                            # PHP: $endDate = duplicate start -> setTime end
                            # if end <= start -> addDay
                            s_end_time_obj = datetime.strptime(sched_end_str, "%H:%M:%S").time()
                            s_end_dt = datetime.combine(s_start_dt.date(), s_end_time_obj)
                            
                            if s_end_dt <= s_start_dt:
                                s_end_dt += timedelta(days=1)
                            
                            # Check if ANY group session completed within [start, end]
                            # Using pre-fetched group_sessions and converting them to datetime
                            
                            is_match = False
                            for gs in group_sessions:
                                # gs.tanggal is Date, gs.jam_patrol is Time
                                gs_dt_str = f"{gs.tanggal} {gs.jam_patrol}"
                                try:
                                    gs_dt = datetime.strptime(gs_dt_str, "%Y-%m-%d %H:%M:%S")
                                    if s_start_dt <= gs_dt <= s_end_dt:
                                        is_match = True
                                        break
                                except:
                                    continue
                            
                            if is_match:
                                patroli_group += 1

                    except Exception as loop_err:
                         print(f"Error in schedule loop: {loop_err}")
                         continue
            
            curr_date += timedelta(days=1)


    except Exception as e:
        print(f"Error calculating patrol KPI: {e}")
        # Fallback values
        patroli_group = 0
        target_patroli = 0

    # 7. Calculate Rates & Scores
    absen_total = izin + sakit + cuti + alfa
    
    hadir_rate = round((hadir / total_hari * 100), 0) if total_hari > 0 else 0
    
    patroli_rate = 0
    if target_patroli > 0:
        patroli_rate = min(100.0, round((patroli_group / target_patroli * 100), 0))
    else:
        patroli_rate = 100.0 if patroli_group > 0 else 0
        
    absen_rate = round(((total_hari - absen_total) / total_hari * 100), 0) if total_hari > 0 else 0
    disiplin_rate = round(((total_hari - alfa) / total_hari * 100), 0) if total_hari > 0 else 0
    
    # Weight: 50% Hadir, 40% Patrol, 10% Absen (Low Leave)
    score = min(100.0, round((hadir_rate * 0.5) + (patroli_rate * 0.4) + (absen_rate * 0.1), 0))

    # 8. Construct Response
    periode_label = ""
    if tipe_laporan == 'harian':
        periode_label = f"{start_date} s/d {end_date}" if start_date != end_date else str(start_date)
    else:
        month_names = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
        m_idx = int(bulan) if bulan else today.month
        m_name = month_names[m_idx] if 1 <= m_idx <= 12 else str(m_idx)
        y_label = str(tahun) if tahun else str(today.year)
        periode_label = f"{m_name} {y_label}"

    return {
        "status": True,
        "data": {
            "karyawan": {
                "nik": karyawan.nik,
                "nama_karyawan": karyawan.nama_karyawan,
                "nama_jabatan": jabatan_nama,
                "nama_dept": dept_nama,
                "nama_cabang": cabang_nama,
                "kode_cabang": karyawan.kode_cabang,
                "kode_dept": karyawan.kode_dept
            },
            "periode": {
                "tipe": tipe_laporan,
                "label": periode_label,
                "bulan": bulan,
                "tahun": tahun,
                "tanggal_dari": start_date_str,
                "tanggal_sampai": end_date_str,
            },
            "kinerja": {
                "total_hari": total_hari,
                "total_jam": total_jam,
                "hadir": hadir,
                "izin": izin,
                "sakit": sakit,
                "cuti": cuti,
                "alfa": alfa,
                "patroli": patroli_individu,
                "target_patroli": target_patroli,
                "hadir_rate": hadir_rate,
                "patroli_rate": patroli_rate,
                "absen_rate": absen_rate,
                "disiplin_rate": disiplin_rate,
                "score": score
            },
            "status_chart": {
                "labels": ["Hadir", "Izin", "Sakit", "Cuti", "Alfa"],
                "values": [hadir, izin, sakit, cuti, alfa]
            },
            "radar_chart": {
                "labels": ["Kehadiran", "Patroli", "Disiplin", "Izin Rendah", "Konsistensi"],
                "values": [hadir_rate, patroli_rate, disiplin_rate, absen_rate, hadir_rate] # Konsistensi reused hadir_rate like PHP
            }
        }
    }
