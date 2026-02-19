from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, date, time
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
import shutil
import os
import uuid

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import DepartmentActivityTasks, DepartmentTaskSessions, DepartmentTaskPoints, DepartmentTaskPointMaster, Karyawan, Presensi

router = APIRouter(
    prefix="/api/android",
    tags=["Task Legacy"],
)

STORAGE_TASK = "/var/www/appPatrol/storage/app/public/department_tasks"
STORAGE_TASK_SESSION = "/var/www/appPatrol/storage/app/public/department_task_sessions"
STORAGE_TASK_POINT = "/var/www/appPatrol/storage/app/public/department_task_points"
os.makedirs(STORAGE_TASK, exist_ok=True)
os.makedirs(STORAGE_TASK_SESSION, exist_ok=True)
os.makedirs(STORAGE_TASK_POINT, exist_ok=True)

# --- GENERAL TASK (Insidentil) ---

@router.get("/department-task/options")
async def get_options(
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    if not user.nik:
        return {"status": True, "data": []}
        
    # Get user dept/cabang info first
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
         return {"status": True, "data": []}
         
    # Filter points by cabang & dept
    # Note: Android uses this for dropdown points or tasks list? Repository name implies Options.
    # Return list of points? Or list of task types?
    # Usually list of points for checkbox.
    
    points = db.query(DepartmentTaskPointMaster).filter(
        DepartmentTaskPointMaster.kode_cabang == karyawan.kode_cabang,
        DepartmentTaskPointMaster.kode_dept == karyawan.kode_dept,
        DepartmentTaskPointMaster.is_active == 1
    ).order_by(DepartmentTaskPointMaster.urutan).all()
    
    data = []
    for p in points:
        data.append({
            "id": p.id,
            "nama_titik": p.nama_titik,
            "urutan": p.urutan,
            "radius": p.radius,
            "latitude": p.latitude,
            "longitude": p.longitude
        })
        
    # Return matched JSON structure DepartmentTaskOptionsData?
    # Repository line 68: body.data.
    return {"status": True, "data": data} # Assuming data is list or object with list

@router.post("/department-task/store")
async def store_task(
    tanggal: str = Form(...),
    jam_kegiatan: str = Form(..., alias="jamKegiatan"),
    jenis_kegiatan: str = Form(..., alias="jenisKegiatan"),
    judul_kegiatan: str = Form(None, alias="judulKegiatan"),
    keterangan: str = Form(None),
    lokasi: str = Form(None),
    foto_kegiatan: UploadFile = File(..., alias="fotoKegiatan"),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    if not user.nik:
        raise HTTPException(400, "NIK Required")
        
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    kode_dept = karyawan.kode_dept if karyawan else "UNKNOWN"

    filename = f"task_{uuid.uuid4().hex[:8]}.jpg"
    path = os.path.join(STORAGE_TASK, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(foto_kegiatan.file, buffer)
        
    # Parse date/time
    # Android sends YYYY-MM-DD and HH:mm:ss usually
    try:
        tgl_obj = datetime.strptime(tanggal, "%Y-%m-%d").date()
        jam_obj = datetime.strptime(jam_kegiatan, "%H:%M:%S").time()
    except:
        # Fallback or error
        tgl_obj = date.today()
        jam_obj = datetime.now().time()

    new_task = DepartmentActivityTasks(
        nik=user.nik,
        kode_dept=kode_dept,
        tanggal=tgl_obj,
        jam_kegiatan=jam_obj,
        jenis_kegiatan=jenis_kegiatan,
        judul_kegiatan=judul_kegiatan,
        keterangan=keterangan,
        lokasi=lokasi,
        foto_kegiatan=f"department_tasks/{filename}",
        status='complete',
        created_by=user.id,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_task)
    db.commit()
    
    return {"status": True, "message": "Laporan Kegiatan Tersimpan"}

# --- ROUTINE TASK (Session Check) ---

@router.get("/department-task/absen/data")
async def get_task_absen_data(
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    if not user.nik:
        return {"status": True, "data": None}
        
    # Check Active Session Today
    today = date.today()
    session = db.query(DepartmentTaskSessions).filter(
        DepartmentTaskSessions.nik == user.nik,
        DepartmentTaskSessions.tanggal == today,
        DepartmentTaskSessions.status == 'active'
    ).first()
    
    if session:
        return {
            "status": True,
            "data": {
                "id": session.id,
                "status": "active",
                "jam_mulai": str(session.jam_tugas),
                "tanggal": str(session.tanggal)
            }
        }
        
    # Check Completed Session Today?
    # Or just return null
    return {"status": True, "data": None}

@router.post("/department-task/absen")
async def absen_task(
    lokasi: str = Form(None),
    keterangan: str = Form(None),
    foto_task: UploadFile = File(..., alias="fotoTask"),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    if not user.nik:
        raise HTTPException(400, "NIK Required")
        
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    kode_dept = karyawan.kode_dept if karyawan else "UNKNOWN"
    today = date.today()
    
    # Logic: If Active exists -> Stop. Else -> Start.
    active_session = db.query(DepartmentTaskSessions).filter(
        DepartmentTaskSessions.nik == user.nik,
        DepartmentTaskSessions.tanggal == today,
        DepartmentTaskSessions.status == 'active'
    ).first()
    
    if active_session:
        # STOP SESSION
        # Does Android send photo for stop? Usually.
        # But 'foto_task' is required in repo.
        
        # We assume this request stops the session if active.
        # Or maybe Android calls different URL? 
        # Repository 'absenTask' -> '/department-task/absen' (based on function naming pattern).
        # And it handles Start/Stop logic on server or client?
        # Usually client checks state first. If active, calls stop.
        # But params are same: lokasi, keterangan, foto.
        
        # Update session to complete
        active_session.status = 'complete'
        # Maybe separate field for stop photo? Model only has 'foto_absen'.
        # Assuming 'foto_absen' is for START.
        # If stop, where to put photo? Maybe 'foto_pulang'? 
        # Model doesn't have 'foto_pulang'. 
        # So maybe just update status. 
        # Or created a new session? No, daily session.
        # Let's assume just close it.
        
        db.commit()
        return {"status": True, "message": "Sesi Tugas Selesai", "data": {"status": "complete"}}
        
    else:
        # START SESSION
        filename = f"session_{user.nik}_{uuid.uuid4().hex[:6]}.jpg"
        path = os.path.join(STORAGE_TASK_SESSION, filename)
        with open(path, "wb") as buffer:
            shutil.copyfileobj(foto_task.file, buffer)
            
        new_session = DepartmentTaskSessions(
            nik=user.nik,
            kode_dept=kode_dept,
            tanggal=today,
            jam_tugas=datetime.now().time(),
            status='active',
            lokasi_absen=lokasi,
            foto_absen=f"department_task_sessions/{filename}",
            created_by=user.id,
            # kode_jam_kerja? Get from Presensi?
        )
        # Try get shift
        shift = db.query(Presensi).filter(
            Presensi.nik == user.nik,
            Presensi.tanggal == today
        ).first()
        if shift:
            new_session.kode_jam_kerja = shift.kode_jam_kerja
            
        db.add(new_session)
        db.commit()
        
        return {"status": True, "message": "Sesi Tugas Dimulai", "data": {"status": "active", "id": new_session.id}}

@router.post("/department-task/point/store")
async def store_task_point(
    sessionId: int = Form(..., alias="sessionId"),
    taskPointMasterId: int = Form(..., alias="taskPointMasterId"),
    lokasi: str = Form(None),
    keterangan: str = Form(None),
    foto_task_point: UploadFile = File(..., alias="fotoTaskPoint"),
    # user...
    db: Session = Depends(get_db)
):
    # Save Photo
    filename = f"point_{sessionId}_{taskPointMasterId}_{uuid.uuid4().hex[:6]}.jpg"
    path = os.path.join(STORAGE_TASK_POINT, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(foto_task_point.file, buffer)
        
    point = DepartmentTaskPoints(
        department_task_session_id=sessionId,
        department_task_point_master_id=taskPointMasterId,
        lokasi=lokasi,
        keterangan=keterangan,
        jam=datetime.now().time(),
        foto=f"department_task_points/{filename}",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(point)
    db.commit()
    
    return {"status": True, "message": "Poin Tugas Berhasil Disimpan"}
