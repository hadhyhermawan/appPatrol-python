
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, date, timedelta
from app.database import get_db
from app.models.models import (
    Violation, Karyawan, Presensi, PresensiJamkerja, Cabang,
    PatrolSchedules, PatrolSessions, DepartmentTaskSessions, Departemen, AppFraud,
    EmployeeLocationHistories
)
from sqlalchemy import func, or_, and_, desc
import shutil
import os
import uuid
from sqlalchemy import text

def get_excluded_niks(db: Session):
    excluded_roles = [
        "Super Admin", 
        "Admin Departemen", 
        "Unit Pelaksana Pelayanan Pelanggan", 
        "Unit Layanan Pelanggan"
    ]
    try:
        query = text("""
            SELECT uk.nik 
            FROM users_karyawan uk
            JOIN model_has_roles mhr ON uk.id_user = mhr.model_id
            JOIN roles r ON mhr.role_id = r.id
            WHERE mhr.model_type = 'App\\\\Models\\\\User'
            AND r.name IN :roles
        """)
        result = db.execute(query, {"roles": tuple(excluded_roles)}).fetchall()
        return [row[0] for row in result]
    except Exception as e:
        print(f"Error fetching excluded NIKs: {e}")
        return []

router = APIRouter(
    prefix="/api/security/violations",
    tags=["Violations"],
    responses={404: {"description": "Not found"}},
)

UPLOAD_DIR = "/var/www/appPatrol/storage/app/public/violations"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("")
def get_violations(
    page: int = 1,
    per_page: int = 10,
    search: Optional[str] = None,
    date_start: Optional[date] = None,
    date_end: Optional[date] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    today = date.today()
    
    # Auto-generate ABSENT violations for today if filter allows or includes today
    # To be safe, we only auto-generate for today to avoid aggressive history filling
    should_sync = False
    if not date_start and not date_end:
        should_sync = True
    elif date_start and date_start <= today and (not date_end or date_end >= today):
        should_sync = True
        
    if should_sync:
        # Re-use scan logic partially or just call scan_violations and filter
        # Ideally we refactor scan_violations to a service function, but for now:
        # We can implement a lightweight check here or call scan_violations(today, db)
        # Note: calling scan_violations is safer as it shares logic
        
        try:
            detected = scan_violations(date_scan=today, db=db)
            
            # Simple deduplication already handled by scan_violations 'is_new' logic 
            # BUT scan_violations returns dicts, doesn't verify DB existence again if scan_violations didn't save.
            # scan_violations currently DOES NOT save. It checks 'is_new' against DB then returns list.
            
            for d in detected:
                # We only want to auto-save 'ABSENT' type
                if d['violation_code'] == 'ABSENT':
                    # Double check existence to be sure (race condition)
                    exists = db.query(Violation).filter(
                        Violation.nik == d['nik'],
                        Violation.tanggal_pelanggaran == today,
                        Violation.violation_type == 'ABSENT'
                    ).first()
                    
                    if not exists:
                        new_v = Violation(
                            nik=d['nik'],
                            tanggal_pelanggaran=today,
                            jenis_pelanggaran='SEDANG', # Default for Absent
                            keterangan=d['description'],
                            sanksi='',
                            status='OPEN',
                            source='SYSTEM',
                            violation_type='ABSENT'
                        )
                        db.add(new_v)
            
            db.commit()
        except Exception as e:
            print(f"Auto-sync failed: {e}")
            # Don't block list fetching

    query = db.query(Violation).join(Karyawan, Violation.nik == Karyawan.nik)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(or_(
            Violation.nik.like(search_filter),
            Karyawan.nama_karyawan.like(search_filter),
            Violation.keterangan.like(search_filter)
        ))
    
    if date_start:
        query = query.filter(Violation.tanggal_pelanggaran >= date_start)
    if date_end:
        query = query.filter(Violation.tanggal_pelanggaran <= date_end)
    
    if type and type != 'all':
        if type == 'absent_late':
            query = query.filter(Violation.violation_type.in_(['ABSENT', 'LATE']))
        elif type == 'absent':
            query = query.filter(Violation.violation_type == 'ABSENT')
        elif type == 'late':
            query = query.filter(Violation.violation_type == 'LATE')
        elif type == 'no_checkout':
            query = query.filter(Violation.violation_type == 'NO_CHECKOUT')
        elif type == 'out_of_location':
            query = query.filter(Violation.violation_type == 'OUT_OF_LOCATION')
        elif type == 'missed_patrol':
            query = query.filter(Violation.violation_type == 'MISSED_PATROL')
        elif type == 'app_force_close':
            query = query.filter(Violation.violation_type == 'FORCE_CLOSE')
        elif type == 'fake_gps':
            query = query.filter(Violation.violation_type == 'FAKE_GPS')
        elif type == 'root_device':
            query = query.filter(Violation.violation_type == 'ROOTED')
        elif type == 'blocked_user':
            query = query.filter(Violation.violation_type == 'BLOCKED')

    total = query.count()
    items = query.order_by(Violation.tanggal_pelanggaran.desc(), Violation.id.desc()).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for item in items:
        result.append({
            "id": item.id,
            "nik": item.nik,
            "nama_karyawan": item.karyawan.nama_karyawan if item.karyawan else "Unknown",
            "tanggal_pelanggaran": item.tanggal_pelanggaran.isoformat(),
            "jenis_pelanggaran": item.jenis_pelanggaran,
            "keterangan": item.keterangan,
            "sanksi": item.sanksi,
            "status": item.status,
            "bukti_foto": f"/storage/violations/{os.path.basename(item.bukti_foto)}" if item.bukti_foto else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "violation_type": item.violation_type,
            "source": item.source
        })

    return result

@router.post("")
async def create_violation(
    nik: str = Form(...),
    tanggal_pelanggaran: date = Form(...),
    jenis_pelanggaran: str = Form(...), # RINGAN, SEDANG, BERAT
    keterangan: str = Form(...),
    sanksi: str = Form(""),
    status: str = Form("OPEN"),
    violation_type: str = Form("MANUAL"),
    bukti_foto: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    path_foto = None
    if bukti_foto:
        filename = f"{uuid.uuid4()}_{bukti_foto.filename}"
        file_location = os.path.join(UPLOAD_DIR, filename)
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(bukti_foto.file, file_object)
        path_foto = file_location

    new_violation = Violation(
        nik=nik,
        tanggal_pelanggaran=tanggal_pelanggaran,
        jenis_pelanggaran=jenis_pelanggaran,
        keterangan=keterangan,
        sanksi=sanksi,
        status=status,
        bukti_foto=path_foto,
        source='SYSTEM' if violation_type != 'MANUAL' else 'MANUAL',
        violation_type=violation_type
    )
    db.add(new_violation)
    db.commit()
    db.refresh(new_violation)
    return {"message": "Violation created", "id": new_violation.id}

@router.delete("/{id}")
def delete_violation(id: int, db: Session = Depends(get_db)):
    violation = db.query(Violation).filter(Violation.id == id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    db.delete(violation)
    db.commit()
    return {"message": "Violation deleted"}

@router.get("/scan")
def scan_violations(
    date_scan: date = Query(default=date.today()),
    db: Session = Depends(get_db)
):
    results = []
    excluded_niks = get_excluded_niks(db)
    
    # Pre-fetch existing violations for this date to avoid duplicates
    existing_violations = db.query(Violation).filter(
        Violation.tanggal_pelanggaran == date_scan
    ).all()
    
    # Create a set of (nik, violation_type) for quick lookup
    # using violation_type column which stores the code e.g. 'LATE', 'ABSENT'
    existing_map = {(v.nik, v.violation_type) for v in existing_violations}

    def is_new(nik, v_code):
        return (nik, v_code) not in existing_map

    # 1. Check Presensi: Late, Absent, No Checkout
    # 1. Check Presensi: Late, Absent, No Checkout
    q_presensi = db.query(Presensi, Karyawan).join(Karyawan, Presensi.nik == Karyawan.nik).filter(Presensi.tanggal == date_scan)
    if excluded_niks:
        q_presensi = q_presensi.filter(Presensi.nik.notin_(excluded_niks))
    presensi_list = q_presensi.all()

    for p, k in presensi_list:
        # Check Late
        # Verify presensi_jamkerja relation exists
        if p.jam_in and p.presensi_jamkerja:
            jam_in_str = str(p.jam_in)
            jam_masuk_str = str(p.presensi_jamkerja.jam_masuk)
            if jam_in_str > jam_masuk_str:
                if is_new(p.nik, 'LATE'):
                    results.append({
                        "nik": p.nik,
                        "nama_karyawan": k.nama_karyawan,
                        "type": "Terlambat",
                        "description": f"Check-in pada {jam_in_str} (Jadwal: {jam_masuk_str})",
                        "timestamp": f"{date_scan} {jam_in_str}",
                        "severity": "RINGAN",
                        "violation_code": "LATE"
                    })

        # Check No Checkout (if applicable)
        # Logic: If date_scan < today AND jam_out is NULL with jam_in.
        if p.jam_in and not p.jam_out and date_scan < date.today():
             if is_new(p.nik, 'NO_CHECKOUT'):
                 results.append({
                    "nik": p.nik,
                    "nama_karyawan": k.nama_karyawan,
                    "type": "Tidak Absen Pulang",
                    "description": "Tidak melakukan checkout",
                    "timestamp": f"{date_scan} 23:59:59",
                    "severity": "RINGAN",
                    "violation_code": "NO_CHECKOUT"
                })

    # Check Absent (Alpha)
    # 1. Users with explicitly marked 'A' status in Presensi table
    q_alpha = db.query(Presensi, Karyawan).join(Karyawan, Presensi.nik == Karyawan.nik).filter(Presensi.tanggal == date_scan, Presensi.status == 'A')
    if excluded_niks:
        q_alpha = q_alpha.filter(Presensi.nik.notin_(excluded_niks))
    alpha_list = q_alpha.all()
    for p, k in alpha_list:
        if is_new(p.nik, 'ABSENT'):
            results.append({
                "nik": p.nik,
                "nama_karyawan": k.nama_karyawan,
                "type": "Tidak Hadir",
                "description": "Tidak hadir tanpa keterangan (Alpha)",
                "timestamp": f"{date_scan} 08:00:00",
                "severity": "SEDANG",
                "violation_code": "ABSENT"
            })

    # 2. Users with Work Schedule but NO Presensi Record at all (Skipped Check-in)
    # Logic:
    # - Active Employees
    # - Not in excluded_niks
    # - Not in presensi_list (already checked in)
    # - Have a schedule for today (Not 'OFF' or Holiday)
    # This is heavy to check for everyone, so limit to Active employees.
    
    # Get all active employees not excluded
    q_active_karyawan = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1')
    if excluded_niks:
        q_active_karyawan = q_active_karyawan.filter(Karyawan.nik.notin_(excluded_niks))
    
    # Filter out those who already have a presensi record for today
    presensi_niks = [p.nik for p, _ in presensi_list] # presensi_list is list of tuples (Presensi, Karyawan)
    q_active_karyawan = q_active_karyawan.filter(Karyawan.nik.notin_(presensi_niks))
    
    potential_absent = q_active_karyawan.all()
    
    # We need to check schedule for each potential absent user
    # Simplified schedule check (replicating logic from absensi_legacy somewhat)
    # 1. Check By Date Extra
    # 2. Check By Date 
    # 3. Check By Day
    # 4. Check Dept Default (Skip for performance? or assumes 'OFF' if not found?)
    # 5. Check User Default (kode_jadwal)
    
    # Helper to check if work day
    from app.models.models import SetJamKerjaByDate, SetJamKerjaByDay, PresensiJamkerjaBydateExtra
    
    day_names = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    scan_day_name = date_scan.strftime("%A") 
    # Python strftime %A is English. Need Indonesian map if DB uses Indo.
    # DB uses Indo: Senin, Selasa...
    english_to_indo = {
        "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu", 
        "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
    }
    scan_day_name_indo = english_to_indo.get(scan_day_name, "Senin")

    for k in potential_absent:
        has_schedule = False
        
        # Check By Date Extra
        extra = db.query(PresensiJamkerjaBydateExtra).filter(
            PresensiJamkerjaBydateExtra.nik == k.nik, 
            PresensiJamkerjaBydateExtra.tanggal == date_scan
        ).first()
        
        if extra:
             # If explicit schedule exists, they should be present.
             # Unless it's an OFF schedule code? Assuming all codes in this table are working shifts.
             has_schedule = True
        else:
             # Check By Date
             by_date = db.query(SetJamKerjaByDate).filter(
                 SetJamKerjaByDate.nik == k.nik,
                 SetJamKerjaByDate.tanggal == date_scan
             ).first()
             
             if by_date:
                 has_schedule = True
             else:
                 # Check By Day
                 by_day = db.query(SetJamKerjaByDay).filter(
                     SetJamKerjaByDay.nik == k.nik,
                     SetJamKerjaByDay.hari == scan_day_name_indo
                 ).first()
                 
                 if by_day:
                     # Check if 'OFF' or 'LIBUR' code? 
                     # Usually codes like 'L001', 'OFF' etc.
                     # Let's assume if it points to a Valid JamKerja, it is a schedule.
                     # We might need to check Is Active or not 'OFF'.
                     # For now, strict: if assigned, must attend.
                     has_schedule = True
                 else:
                     # Check User Default
                     if k.kode_jadwal:
                         has_schedule = True
        
        if has_schedule:
             # One last check: Is it a Holiday (Hari Libur)?
             # Check HariLibur table for this Cabang
             # If holiday, skip absent
             is_holiday = db.query(Cabang).join(Cabang.hari_libur).filter(
                 Cabang.kode_cabang == k.kode_cabang, 
                 # HariLibur.tanggal == date_scan (Need proper join/filter)
                 # Revisit HariLibur model relationship: Cabang -> HariLibur
             ).count()
             
             # Direct HariLibur query is safer
             from app.models.models import HariLibur
             holiday = db.query(HariLibur).filter(
                 HariLibur.tanggal == date_scan, 
                 HariLibur.kode_cabang == k.kode_cabang
             ).first()
             
             if not holiday:
                 if is_new(k.nik, 'ABSENT'):
                    results.append({
                        "nik": k.nik,
                        "nama_karyawan": k.nama_karyawan,
                        "type": "Tidak Hadir",
                        "description": "Memiliki jadwal kerja tetapi tidak hadir (Alpha)",
                        "timestamp": f"{date_scan} 08:00:00",
                        "severity": "SEDANG",
                        "violation_code": "ABSENT"
                    })

    # 2. Blocked Users (Inactive Karyawan)
    # If tanggal_nonaktif is present, they are blocked/inactive
    # Only report if they tried to do something today?
    # Or just report all inactive users? Reporting all is noisy.
    # User asked for "karyawan yang terblokir". Maybe simple list.
    q_blocked = db.query(Karyawan).filter(Karyawan.tanggal_nonaktif != None)
    if excluded_niks:
        q_blocked = q_blocked.filter(Karyawan.nik.notin_(excluded_niks))
    blocked = q_blocked.limit(50).all()
    for k in blocked:
        if is_new(k.nik, 'BLOCKED'):
            results.append({
                "nik": k.nik,
                "nama_karyawan": k.nama_karyawan,
                "type": "Karyawan Nonaktif/Blokir",
                "description": f"Status karyawan non-aktif sejak {k.tanggal_nonaktif}",
                "timestamp": f"{date_scan} 00:00:00",
                "severity": "BERAT",
                "violation_code": "BLOCKED"
            })

    # 3. Missed Patrol
    # Filter only Security Dept (e.g., UK3, SEC)
    # This is a bit weak without strict schedule binding.
    # Check if they are PRESENT but have 0 patrol sessions
    security_present = [(p, k) for p, k in presensi_list if k.kode_dept in ['SEC', 'UK3', 'SAT'] and p.status == 'H']

    for p, k in security_present:
        patrol_count = db.query(PatrolSessions).filter(
            PatrolSessions.nik == p.nik,
            PatrolSessions.tanggal == date_scan
        ).count()

        if patrol_count == 0:
            if is_new(p.nik, 'MISSED_PATROL'):
                results.append({
                    "nik": p.nik,
                    "nama_karyawan": k.nama_karyawan,
                    "type": "Tidak Patroli",
                    "description": "Hadir tetapi tidak melakukan patroli satupun",
                    "timestamp": f"{date_scan} 12:00:00",
                    "severity": "SEDANG",
                    "violation_code": "MISSED_PATROL"
                })

    # 4. App Fraud (Fake GPS, Force Close, Rooted)
    # 4. App Fraud
    q_frauds = db.query(AppFraud).filter(func.date(AppFraud.timestamp) == date_scan)
    if excluded_niks:
        q_frauds = q_frauds.filter(AppFraud.nik.notin_(excluded_niks))
    frauds = q_frauds.all()

    label_map = {
        'FAKE_GPS': 'Terdeteksi Fake GPS',
        'FORCE_CLOSE': 'Aplikasi Force Close',
        'ROOT_DEVICE': 'Perangkat Rooted'
    }

    for f in frauds:
        violation_code = f.fraud_type
        # Only process known types or just pass through
        label = label_map.get(violation_code, violation_code)
        
        # Severity
        sev = 'SEDANG'
        if violation_code in ['FAKE_GPS', 'ROOT_DEVICE']:
            sev = 'BERAT'
            
        if is_new(f.nik, violation_code):
            results.append({
                "nik": f.nik,
                "nama_karyawan": f.karyawan.nama_karyawan if f.karyawan else f.nik,
                "type": label,
                "description": f.description or "Terdeteksi aktivitas mencurigakan pada aplikasi",
                "timestamp": str(f.timestamp),
                "severity": sev,
                "violation_code": violation_code
            })

    # 5. Laravel Mock Location Check (EmployeeLocationHistories.is_mocked = 1)
    # This might overlap with AppFraud(FAKE_GPS), but we check both sources as requested.
    q_mocked = db.query(EmployeeLocationHistories).filter(
        func.date(EmployeeLocationHistories.recorded_at) == date_scan,
        EmployeeLocationHistories.is_mocked == 1
    )
    if excluded_niks:
        q_mocked = q_mocked.filter(EmployeeLocationHistories.nik.notin_(excluded_niks))
    mocked_locs = q_mocked.all()

    for m in mocked_locs:
        if is_new(m.nik, 'FAKE_GPS'):
             # Need to fetch employee name manually or join query
             karyawan = db.query(Karyawan).filter(Karyawan.nik == m.nik).first()
             results.append({
                "nik": m.nik,
                "nama_karyawan": karyawan.nama_karyawan if karyawan else m.nik,
                "type": "Terdeteksi Fake GPS (System)",
                "description": "Lokasi palsu terdeteksi oleh sistem pelacakan",
                "timestamp": str(m.recorded_at),
                "severity": "BERAT",
                "violation_code": "FAKE_GPS"
            })

    # 6. Out of Location / Radius Violation (Simplified Logic)
    # Replicating Laravel's complex SQL in Python ORM is heavy.
    # For now, we check Presensi locations if they are far from office.
    # We will assume a simple check: if Presensi has checked in but location (jam_in) is suspicious.
    # Ideally, this needs Haversine calc against Cabang location.
    # Implementing a basic version:
    
    # Get active presensi with check-in data
    q_active = db.query(Presensi, Karyawan, Cabang).join(
        Karyawan, Presensi.nik == Karyawan.nik
    ).join(
        Cabang, Karyawan.kode_cabang == Cabang.kode_cabang
    ).filter(
        Presensi.tanggal == date_scan,
        Presensi.jam_in != None,
        Presensi.lokasi_in != None,
        Cabang.lokasi_cabang != None,
        Cabang.radius_cabang > 0,
        Karyawan.lock_location == '1'
    )
    
    if excluded_niks:
        q_active = q_active.filter(Karyawan.nik.notin_(excluded_niks))
        
    active_presensi = q_active.all()

    for p, k, c in active_presensi:
        try:
            # Parse lat,long from strings "lat,long"
            user_lat, user_long = map(float, p.lokasi_in.split(','))
            office_lat, office_long = map(float, c.lokasi_cabang.split(','))
            
            # Haversine Formula
            import math
            R = 6371000 # Earth radius in meters
            dLat = math.radians(office_lat - user_lat)
            dLon = math.radians(office_long - user_long)
            a = math.sin(dLat/2) * math.sin(dLat/2) + \
                math.cos(math.radians(user_lat)) * math.cos(math.radians(office_lat)) * \
                math.sin(dLon/2) * math.sin(dLon/2)
            c_val = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = R * c_val
            
            if distance > c.radius_cabang:
                 if is_new(k.nik, 'OUT_OF_LOCATION'):
                    results.append({
                        "nik": k.nik,
                        "nama_karyawan": k.nama_karyawan,
                        "type": "Di Luar Radius Kantor",
                        "description": f"Absen di luar radius ({int(distance)}m > {c.radius_cabang}m)",
                        "timestamp": str(p.jam_in),
                        "severity": "SEDANG",
                        "violation_code": "OUT_OF_LOCATION"
                    })

        except Exception as e:
            # Skip invalid coordinates
            continue

    return results
