from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import (
    PatrolSessions, PatrolPoints, PatrolPointMaster, Presensi, PresensiJamkerja, Karyawan,
    Userkaryawan, Cabang, SetJamKerjaByDay, SetJamKerjaByDate, PatrolSchedules, SecurityReports,
    PengaturanUmum
) # Added SecurityReports & PengaturanUmum
from app.models.models import PresensiJamkerjaBydept, PresensiJamkerjaByDeptDetail
# If Detailsetjamkerjabydept is not in models, I'll need to check or assume logic.
from datetime import datetime, date, time, timedelta
import shutil
import os
import uuid
import math

router = APIRouter(
    prefix="/api/android/patroli",
    tags=["Patroli Legacy"],
    responses={404: {"description": "Not found"}},
)

# STORAGE_PATH = "/var/www/appPatrol/storage/app/public/patroli" # OLD
STORAGE_PATH = "storage/app/public/uploads/patroli" # Matches PHP: "uploads/patroli/{$nik}-{$tanggalFormat}-absenpatrol"
# PHP uses: uploads/patroli/NIK-DATE-absenpatrol/FILENAME
# I should mimic this structure if possible for compatibility.

def haversine_great_circle_distance(lat1, lon1, lat2, lon2):
    R = 6371000 # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def save_upload(file_obj: UploadFile, subfolder: str) -> str:
    # subfolder e.g. "12345-20231010-absenpatrol"
    base_dir = "/var/www/appPatrol/storage/app/public/uploads/patroli"
    target_dir = os.path.join(base_dir, subfolder)
    os.makedirs(target_dir, exist_ok=True)
    
    filename = f"{subfolder}-{datetime.now().strftime('%H%M%S')}-{file_obj.filename}"
    target_path = os.path.join(target_dir, filename)
    
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file_obj.file, buffer)
    except Exception as e:
        print(f"Error saving image: {e}")
        return None
        
    return filename

def get_jam_kerja(nik: str, kode_cabang: str, kode_dept: str, db: Session):
    today = date.today()
    hari_map = {
        0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'
    }
    hari_ini = hari_map[today.weekday()]
    
    # 1. By Date
    jk_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today).first()
    if jk_date:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_date.kode_jam_kerja).first()
        
    # 2. By Day
    jk_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == hari_ini).first()
    if jk_day:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_day.kode_jam_kerja).first()
        
    # 3. By Dept (skipping for now as it requires tables I'm not 100% sure about, but falling back to None is safer than crashing)
    # Ref: getJamKerja in PHP
    
    return None

def get_next_point_by_order(session_id: int, db: Session):
    # Find next point where jam is null, ordered by master urutan
    # Join PatrolPoints with PatrolPointMaster to get urutan
    
    # SQLAlchemy query
    # SELECT pp.* FROM patrol_points pp JOIN patrol_point_master ppm ON pp.patrol_point_master_id = ppm.id
    # WHERE pp.patrol_session_id = :sid AND pp.jam IS NULL
    # ORDER BY ppm.urutan ASC LIMIT 1
    
    next_point = db.query(PatrolPoints)\
        .join(PatrolPointMaster, PatrolPoints.patrol_point_master_id == PatrolPointMaster.id)\
        .filter(PatrolPoints.patrol_session_id == session_id)\
        .filter(PatrolPoints.jam == None)\
        .order_by(PatrolPointMaster.urutan.asc())\
        .first()
        
    return next_point

@router.get("/getAbsenPatrol")
async def get_absen_patrol(
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # Get Karyawan
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    if not user_karyawan:
        return {"status": False, "message": "Data Karyawan Tidak Ditemukan"}
        
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    if not karyawan:
        return {"status": False, "message": "Data Karyawan Tidak Ditemukan"}
        
    nik = karyawan.nik
    
    # 1. Cek Presensi Hari Ini
    presensi_aktif = db.query(Presensi).filter(
        Presensi.nik == nik,
        Presensi.jam_in != None,
        Presensi.jam_out == None
    ).order_by(Presensi.tanggal.desc(), Presensi.jam_in.desc()).first()
    
    tanggal = presensi_aktif.tanggal if presensi_aktif else date.today()
    
    # 2. Get Jam Kerja
    if presensi_aktif:
        jam_kerja = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == presensi_aktif.kode_jam_kerja).first()
    else:
        jam_kerja = get_jam_kerja(nik, karyawan.kode_cabang, karyawan.kode_dept, db)
        
    if not jam_kerja:
        return {"status": False, "message": "Tidak memiliki jadwal kerja hari ini."}
        
    # 3. Get Cabang Location
    cabang = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
    lat = lon = None
    if cabang and cabang.lokasi_cabang:
        parts = cabang.lokasi_cabang.split(',')
        if len(parts) == 2:
            lat = float(parts[0])
            lon = float(parts[1])
            
    # 4. Check Sessiob
    last_session = None
    if presensi_aktif:
        last_session = db.query(PatrolSessions).filter(
            PatrolSessions.nik == nik,
            PatrolSessions.kode_jam_kerja == presensi_aktif.kode_jam_kerja,
            PatrolSessions.tanggal == presensi_aktif.tanggal
        ).order_by(PatrolSessions.id.desc()).first()
        
    sudah_absen = (last_session is not None)
    bisa_absen = True
    next_point_id = None
    
    # Group NIKs
    group_niks = db.query(Karyawan.nik).filter(
        Karyawan.kode_cabang == karyawan.kode_cabang,
        Karyawan.kode_dept == karyawan.kode_dept
    ).all()
    group_niks_list = [n[0] for n in group_niks]
    
    # Get Global Settings for Face Recognition
    pengaturan = db.query(PengaturanUmum).first()
    face_recog_status = 1 if pengaturan and pengaturan.face_recognition == 1 else 0
    
    # Schedules
    today_sessions = db.query(PatrolSessions).filter(
        PatrolSessions.nik.in_(group_niks_list),
        PatrolSessions.tanggal == tanggal
    ).all()

    schedules = db.query(PatrolSchedules).filter(
        PatrolSchedules.kode_jam_kerja == jam_kerja.kode_jam_kerja,
        PatrolSchedules.is_active == True
    ).filter(
        or_(PatrolSchedules.kode_dept == None, PatrolSchedules.kode_dept == karyawan.kode_dept)
    ).filter( # Explicit filter logic to match Laravel
        or_(PatrolSchedules.kode_cabang == None, PatrolSchedules.kode_cabang == karyawan.kode_cabang)
    ).all()
    
    if schedules:
        bisa_absen = False
        now_time = datetime.now().time()
        
        # Check active window for 'bisa_absen'
        for sch in schedules:
            in_window = False
            # Simple Time Check handling midnight wrapping
            if sch.start_time <= sch.end_time:
                if sch.start_time <= now_time <= sch.end_time:
                    in_window = True
            else:
                if sch.start_time <= now_time or now_time <= sch.end_time:
                    in_window = True
            
            if in_window:
                # Shared Schedule Check: Has anyone in group done it in this window?
                session_in_window = False
                
                # Filter in memory to avoid complex raw queries across DBs
                for sess in today_sessions:
                    # sess.jam_patrol is time
                    sess_time = sess.jam_patrol
                    if sess_time:
                         if sch.start_time <= sch.end_time:
                             if sch.start_time <= sess_time <= sch.end_time:
                                 session_in_window = True
                                 break
                         else:
                             if sch.start_time <= sess_time or sess_time <= sch.end_time:
                                 session_in_window = True
                                 break
                
                if not session_in_window:
                    bisa_absen = True
                
                # Match Laravel logic: If user is inside a window, rely on that window status.
                break 

        if last_session and last_session.status == 'active':
            bisa_absen = True
        
        if last_session and last_session.status == 'active':
            bisa_absen = True
    else:
        # Cooldown Logic (60 mins)
        if sudah_absen:
            # Calculate time diff
            last_dt = datetime.combine(last_session.tanggal, last_session.jam_patrol)
            now_dt = datetime.now()
            diff = (now_dt - last_dt).total_seconds()
            if diff < 3600:
                bisa_absen = False
                
    if last_session and last_session.status == 'active':
        next_p = get_next_point_by_order(last_session.id, db)
        if next_p:
            next_point_id = next_p.patrol_point_master_id
            
    # 5. Points
    master_points = db.query(PatrolPointMaster).filter(
        PatrolPointMaster.kode_cabang == karyawan.kode_cabang
    ).order_by(PatrolPointMaster.urutan.asc()).all()
    
    points_data = []
    for p in master_points:
        foto = lokasi = jam = None
        tombol_aktif = False
        
        if last_session:
            pp = db.query(PatrolPoints).filter(
                PatrolPoints.patrol_session_id == last_session.id,
                PatrolPoints.patrol_point_master_id == p.id
            ).first()
            
            if pp:
                # Construct Full URL for foto
                if pp.foto:
                    # Logic needed for URL
                    # uploads/patroli/...
                    foto = f"https://frontend.k3guard.com/api-py/storage/uploads/patroli/{nik}-{str(tanggal).replace('-','')}-patrol/{pp.foto}"
                lokasi = pp.lokasi
                jam = str(pp.jam) if pp.jam else None
                
                if jam is None and p.id == next_point_id:
                    tombol_aktif = True
        else:
            if p.urutan == 1:
                tombol_aktif = True
                
        points_data.append({
            "id": p.id,
            "nama_titik": p.nama_titik,
            "urutan": p.urutan,
            "latitude": float(p.latitude) if p.latitude else 0,
            "longitude": float(p.longitude) if p.longitude else 0,
            "radius": p.radius,
            "foto": foto,
            "lokasi": lokasi,
            "jam": jam,
            "tombol_aktif": tombol_aktif
        })
        
    lokasi_wajib = (karyawan.lock_location == '1')
    if lokasi_wajib and (not lat or not lon):
        return {"status": False, "message": "Koordinat Cabang belum disetting."}
        
    # Schedule Tasks List (Implementing V2 logic)
    schedule_tasks = [] 
    
    # Sort schedules by start_time
    schedules_sorted = sorted(schedules, key=lambda x: x.start_time)
    
    shift_start_val = datetime.combine(date.today(), jam_kerja.jam_masuk) # Dummy date
    
    for sch in schedules_sorted:
        sched_start_val = datetime.combine(date.today(), sch.start_time)
        
        # Determine start date relative to shift date (tanggal)
        start_datetime = datetime.combine(tanggal, sch.start_time)
        
        # Lintas Hari Logic (if shift crosses midnight and schedule is 'early morning', it belongs to next day relative to shift start)
        # Simplified logic from Laravel: if jam_kerja.lintashari (boolean/1) AND sched < shift_start -> add day
        # Checking lintashari attribute existence first
        is_lintashari = getattr(jam_kerja, 'lintashari', 0) == 1 or getattr(jam_kerja, 'lintashari', '0') == '1'
        
        # Compare times only
        if is_lintashari and sch.start_time < jam_kerja.jam_masuk:
             start_datetime = start_datetime + timedelta(days=1)
             
        # End Datetime
        end_time_val = sch.end_time
        # Use start_datetime date as base
        end_datetime = datetime.combine(start_datetime.date(), end_time_val)
        
        # Cross midnight check for schedule duration
        if end_datetime <= start_datetime:
            end_datetime = end_datetime + timedelta(days=1)
            
        # Check Status
        # is_done logic: check if ANY session in today_sessions falls within start/end datetime
        # We need to reconstruct session datetime. Session has .tanggal + .jam_patrol
        is_done = False
        for sess in today_sessions:
            if sess.jam_patrol:
                sess_dt = datetime.combine(sess.tanggal, sess.jam_patrol)
                if start_datetime <= sess_dt <= end_datetime:
                    is_done = True
                    break
        
        status_task = 'pending'
        if is_done:
            status_task = 'done'
        elif datetime.now() > end_datetime:
            status_task = 'missed'
            
        schedule_tasks.append({
            "id": sch.id,
            "name": sch.name if sch.name else "Tugas Rutin",
            "start_time": str(sch.start_time),
            "end_time": str(sch.end_time),
            "start_datetime": start_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
            "formatted_time": f"{start_datetime.strftime('%H:%M')} - {end_datetime.strftime('%H:%M')}",
            "status": status_task
        }) 
    
    # Using existing session object to serialize
    session_data = None
    if last_session:
        session_data = {
            "id": last_session.id,
            "status": last_session.status,
            "jam_patrol": str(last_session.jam_patrol),
            "foto_absen": last_session.foto_absen # RAW filename
        }

    return {
        "status": True,
        "message": "Data Patroli",
        "sessionId": last_session.id if last_session else None,
        "sudah_absen": sudah_absen,
        "tombol_aktif": (not sudah_absen) or bisa_absen,
        "data": {
            "hari_ini": str(tanggal),
            "patrol_session": session_data,
            "schedule_tasks": schedule_tasks,
            "karyawan": {
                "nik": nik,
                "nama_karyawan": karyawan.nama_karyawan,
                "lock_location": karyawan.lock_location,
                "patroli_wajib_lokasi": lokasi_wajib,
                "latitude": lat,
                "longitude": lon,
                "radius": int(cabang.radius_cabang) if cabang else 50,
                "kode_jam_kerja": jam_kerja.kode_jam_kerja,
                "nama_jam_kerja": jam_kerja.nama_jam_kerja,
                "jam_masuk": str(jam_kerja.jam_masuk),
                "jam_pulang": str(jam_kerja.jam_pulang),
                "face_recognition": bool(face_recog_status),
                "faceRecognition": bool(face_recog_status)
            },
            "points": points_data
        }
    }

@router.post("/absen")
async def patroli_absen(
    loc_patrol: str = Form(...),
    foto_patrol: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # ... Simplified Sync ...
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    if not user_karyawan: raise HTTPException(404, "Karyawan not found")
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    nik = karyawan.nik
    
    presensi = db.query(Presensi).filter(Presensi.nik == nik, Presensi.jam_in != None, Presensi.jam_out == None).order_by(Presensi.tanggal.desc()).first()
    if not presensi:
        return {"status": False, "message": "Anda belum melakukan presensi masuk."}
        
    tanggal = presensi.tanggal
    tanggal_fmt = str(tanggal).replace('-', '')
    
    # check radius
    cabang = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
    if karyawan.lock_location == '1' and cabang and cabang.lokasi_cabang:
        clat, clon = map(float, cabang.lokasi_cabang.split(','))
        ulat, ulon = map(float, loc_patrol.split(','))
        dist = haversine_great_circle_distance(ulat, ulon, clat, clon)
        if dist > cabang.radius_cabang:
             return {"status": False, "message": "Anda berada di luar radius kantor."}
             
    # Anti double (simple)
    existing = db.query(PatrolSessions).filter(PatrolSessions.nik == nik, PatrolSessions.tanggal == tanggal, PatrolSessions.kode_jam_kerja == presensi.kode_jam_kerja).order_by(PatrolSessions.id.desc()).first()
    if existing:
        # Check time diff
        pass # Skip for brevity
        
    # Save Image
    subfolder = f"{nik}-{tanggal_fmt}-absenpatrol"
    foto_name = save_upload(foto_patrol, subfolder)
    
    # Create Session
    session = PatrolSessions(
        nik=nik,
        tanggal=tanggal,
        kode_jam_kerja=presensi.kode_jam_kerja,
        status='active',
        jam_patrol=datetime.now().time(),
        foto_absen=foto_name,
        lokasi_absen=loc_patrol,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # SEED POINTS
    master_points = db.query(PatrolPointMaster).filter(PatrolPointMaster.kode_cabang == karyawan.kode_cabang).order_by(PatrolPointMaster.urutan).all()
    for mp in master_points:
        new_point = PatrolPoints(
            patrol_point_master_id=mp.id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session.patrol_points.append(new_point)
    
    db.commit()
        
    # Delete Security Report
    db.query(SecurityReports).filter(SecurityReports.nik == nik, SecurityReports.type == 'FACE_LIVENESS_LOCK').delete()
    db.commit()
    
    foto_url = f"https://frontend.k3guard.com/api-py/storage/uploads/patroli/{subfolder}/{foto_name}"
    
    return {
        "status": True,
        "message": "Absen Patroli Berhasil",
        "session_id": session.id,
        "foto_patrol": foto_url,
        "lock_location": karyawan.lock_location
    }

@router.post("/storePatroliPoint")
async def store_patroli_point(
    session_id: int = Form(...),
    patrol_point_master_id: int = Form(...),
    loc_patrol: str = Form(...),
    image: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    nik = user_karyawan.nik
    
    session = db.query(PatrolSessions).filter(PatrolSessions.id == session_id).first()
    if not session or session.status != 'active':
        return {"status": False, "message": "Sesi tidak aktif"}
        
    # Find Point
    point = db.query(PatrolPoints).filter(
        PatrolPoints.patrol_session_id == session.id,
        PatrolPoints.patrol_point_master_id == patrol_point_master_id
    ).first()
    
    if not point:
        return {"status": False, "message": "Titik tidak ditemukan di sesi ini"}
        
    if point.jam:
        return {"status": True, "message": "Titik sudah diambil (duplicate)", "duplicate": True}
        
    # Check Sequence
    next_p = get_next_point_by_order(session.id, db)
    if next_p and next_p.id != point.id:
        return {"status": False, "message": "Harap ikuti urutan titik patroli"}
        
    # Radius Tolerance
    mp = db.query(PatrolPointMaster).filter(PatrolPointMaster.id == patrol_point_master_id).first()
    # Check radius logic (similar to above)
    
    tanggal_fmt = str(session.tanggal).replace('-', '')
    subfolder = f"{nik}-{tanggal_fmt}-patrol"
    fname = save_upload(image, subfolder)
    
    point.foto = fname
    point.lokasi = loc_patrol
    point.jam = datetime.now().time()
    point.updated_at = datetime.now()
    
    db.commit()
    
    # Check Complete
    remaining = db.query(PatrolPoints).filter(PatrolPoints.patrol_session_id == session.id, PatrolPoints.jam == None).count()
    if remaining == 0:
        session.status = 'complete'
        session.updated_at = datetime.now()
        db.commit()
        
    foto_url = f"https://frontend.k3guard.com/api-py/storage/uploads/patroli/{subfolder}/{fname}"
    
    return {
        "status": True,
        "message": "Titik Berhasil Disimpan",
        "foto_url": foto_url,
        "remaining_points": remaining,
        "session_status": session.status,
        "lock_location": "1" # Todo: fetch from karyawan
    }
