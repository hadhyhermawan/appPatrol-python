from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import desc, text, or_, and_
import uuid
import shutil
import os

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import (
    PresensiIzinabsen, PresensiIzinsakit, PresensiIzincuti, PresensiIzindinas, Cuti, Userkaryawan, Karyawan
)

router = APIRouter(
    prefix="/api/android",
    tags=["Izin Legacy"],
)

# Storage Path (Laravel Compatibility)
STORAGE_PATH_IZIN = "/var/www/appPatrol/storage/app/public/izin"
STORAGE_PATH_SAKIT = "/var/www/appPatrol/storage/app/public/izin_sakit" # Matches PHP 'izin_sakit' folder
os.makedirs(STORAGE_PATH_IZIN, exist_ok=True)
os.makedirs(STORAGE_PATH_SAKIT, exist_ok=True)

# --- HELPERS ---

def buat_kode(last_code: str | None, prefix: str, digit: int) -> str:
    # Logic: If last_code starts with prefix, increment suffix. Else 1.
    # Ex: IS26020001
    
    number = 1
    if last_code and last_code.startswith(prefix):
        # Extract suffix
        suffix = last_code[len(prefix):]
        if suffix.isdigit():
            number = int(suffix) + 1
            
    return f"{prefix}{str(number).zfill(digit)}"

def check_conflict(nik: str, dari: date, sampai: date, db: Session, exclude_type: str = None, exclude_id = None):
    # Check overlapping dates in all 3 tables
    
    # Logic: (StartA <= EndB) and (EndA >= StartB)
    
    # 1. Absen
    q_absen = db.query(PresensiIzinabsen).filter(
        PresensiIzinabsen.nik == nik,
        or_(
            and_(PresensiIzinabsen.dari <= sampai, PresensiIzinabsen.sampai >= dari)
        )
    )
    if q_absen.first(): return True
    
    # 2. Sakit
    q_sakit = db.query(PresensiIzinsakit).filter(
        PresensiIzinsakit.nik == nik,
        or_(
            and_(PresensiIzinsakit.dari <= sampai, PresensiIzinsakit.sampai >= dari)
        )
    )
    if q_sakit.first(): return True
    
    # 3. Cuti
    q_cuti = db.query(PresensiIzincuti).filter(
        PresensiIzincuti.nik == nik,
        or_(
            and_(PresensiIzincuti.dari <= sampai, PresensiIzincuti.sampai >= dari)
        )
    )
    if q_cuti.first(): return True
    
    # 4. Dinas? Usually Dinas doesn't block Absen, but Absen blocks Dinas?
    # PHP code checks conflict against Absen, Sakit, Cuti only.
    
    return False

# --- IZIN ABSEN ---

@router.get("/izin-absen")
async def list_izin_absen(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    page: int = 1,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    nik = user.nik
    if not nik: return {"status": False, "message": "NIK not found"}
    
    query = db.query(PresensiIzinabsen, Karyawan.nama_karyawan)\
        .join(Karyawan, PresensiIzinabsen.nik == Karyawan.nik)\
        .filter(PresensiIzinabsen.nik == nik)
        
    if dari and sampai:
        query = query.filter(PresensiIzinabsen.tanggal >= dari, PresensiIzinabsen.tanggal <= sampai)
        
    if status is not None:
        query = query.filter(PresensiIzinabsen.status == status)
        
    total = query.count()
    results = query.order_by(desc(PresensiIzinabsen.tanggal))\
        .offset((page-1)*limit).limit(limit).all()
        
    data = []
    for r, nama in results:
        # Map Status
        # 0: Pending, 1: Approved, 2: Rejected
        st_text = "Pending"
        if r.status == 1 or r.status == '1': st_text = "Disetujui"
        elif r.status == 2 or r.status == '2': st_text = "Ditolak"
        
        data.append({
            "kode_izin": r.kode_izin,
            "tanggal": str(r.tanggal),
            "dari": str(r.dari),
            "sampai": str(r.sampai),
            "keterangan": r.keterangan,
            "status": r.status, # Keep raw for app logic
            "status_text": st_text,
            "nama_karyawan": nama
        })
        
    return {
        "status": True,
        "data": {
            "current_page": page,
            "data": data,
            "total": total
        }
    } # Match Laravel Pagination Structure loosely or adapt

@router.post("/izin-absen/store")
async def store_izin_absen(
    dari: str = Form(...),
    sampai: str = Form(...),
    keterangan: str = Form(...),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    nik = user.nik
    
    d_dari = datetime.strptime(dari, "%Y-%m-%d").date()
    d_sampai = datetime.strptime(sampai, "%Y-%m-%d").date()
    
    # 1. Check Conflict
    if check_conflict(nik, d_dari, d_sampai, db):
        raise HTTPException(400, "Sudah ada pengajuan izin lain pada tanggal tersebut")
        
    # 2. Generate Code: IA + YYMM + 000X
    prefix = f"IA{d_dari.strftime('%y%m')}"
    last = db.query(PresensiIzinabsen).filter(PresensiIzinabsen.kode_izin.like(f"{prefix}%"))\
        .order_by(desc(PresensiIzinabsen.kode_izin)).first()
    
    last_code = last.kode_izin if last else None
    kode = buat_kode(last_code, prefix, 4)
    
    new_izin = PresensiIzinabsen(
        kode_izin=kode,
        nik=nik,
        tanggal=d_dari, # Tanggal pengajuan = Dari? Or Today? PHP uses dari.
        dari=d_dari,
        sampai=d_sampai,
        keterangan=keterangan,
        status=0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_izin)
    db.commit()
    
    return {"status": True, "message": "Izin berhasil diajukan", "data": new_izin}

# --- IZIN SAKIT ---

@router.get("/izin-sakit")
async def list_izin_sakit(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    nik = user.nik
    query = db.query(PresensiIzinsakit, Karyawan.nama_karyawan)\
        .join(Karyawan, PresensiIzinsakit.nik == Karyawan.nik)\
        .filter(PresensiIzinsakit.nik == nik)
        
    if dari and sampai:
        query = query.filter(PresensiIzinsakit.tanggal >= dari, PresensiIzinsakit.tanggal <= sampai)
        
    if status is not None:
        query = query.filter(PresensiIzinsakit.status == status)
        
    total = query.count()
    results = query.order_by(desc(PresensiIzinsakit.tanggal))\
        .offset((page-1)*limit).limit(limit).all()
        
    data = []
    for r, nama in results:
        # Fix doc path: if stored as /filename, prepend storage url
        doc_url = None
        if r.doc_sid:
            # PHP stores "/filename.jpg" -> "storage/izin_sakit/filename.jpg"
            clean_path = r.doc_sid.lstrip('/')
            doc_url = f"https://frontend.k3guard.com/api-py/storage/izin_sakit/{clean_path}" # Temp fix url
            
        data.append({
            "kode_izin_sakit": r.kode_izin_sakit,
            "tanggal": str(r.tanggal),
            "dari": str(r.dari),
            "sampai": str(r.sampai),
            "keterangan": r.keterangan,
            "status": r.status,
            "doc_sid": r.doc_sid, # Raw
            "doc_url": doc_url,
            "nama_karyawan": nama
        })
        
    return {
        "status": True, 
        "data": {
            "current_page": page,
            "data": data,
            "total": total
        }
    }

@router.post("/izin-sakit/store")
async def store_izin_sakit(
    dari: str = Form(...),
    sampai: str = Form(...),
    keterangan: str = Form(...),
    foto_bukti: UploadFile = File(None),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    nik = user.nik
    d_dari = datetime.strptime(dari, "%Y-%m-%d").date()
    d_sampai = datetime.strptime(sampai, "%Y-%m-%d").date()

    # 1. Generate Code: IS + YYMM + 000X
    prefix = f"IS{d_dari.strftime('%y%m')}"
    last = db.query(PresensiIzinsakit).filter(PresensiIzinsakit.kode_izin_sakit.like(f"{prefix}%"))\
        .order_by(desc(PresensiIzinsakit.kode_izin_sakit)).first()
        
    last_code = last.kode_izin_sakit if last else None
    kode = buat_kode(last_code, prefix, 4)
    
    # 2. Upload
    foto_path = None
    if foto_bukti:
        ext = foto_bukti.filename.split('.')[-1]
        filename = f"{kode}.{ext}"
        target_path = os.path.join(STORAGE_PATH_SAKIT, filename)
        
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(foto_bukti.file, buffer)
            
        foto_path = "/" + filename # PHP stores with leading slash? Check logic. 
        # PHP: $foto_path = "/" . $filename; confirm.
    
    new_sakit = PresensiIzinsakit(
        kode_izin_sakit=kode,
        nik=nik,
        id_user=user.id,
        tanggal=d_dari,
        dari=d_dari,
        sampai=d_sampai,
        keterangan=keterangan,
        doc_sid=foto_path,
        status=0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_sakit)
    db.commit()
    
    return {"status": True, "message": "Izin sakit berhasil diajukan", "data": new_sakit}


# --- IZIN CUTI ---

@router.get("/izin-cuti")
async def list_izin_cuti(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    nik = user.nik
    query = db.query(PresensiIzincuti, Karyawan.nama_karyawan, Cuti.jenis_cuti)\
        .join(Karyawan, PresensiIzincuti.nik == Karyawan.nik)\
        .join(Cuti, PresensiIzincuti.kode_cuti == Cuti.kode_cuti)\
        .filter(PresensiIzincuti.nik == nik)
        
    if dari and sampai:
        query = query.filter(PresensiIzincuti.dari >= dari, PresensiIzincuti.dari <= sampai) # Note: PHP uses dari
        
    total = query.count()
    results = query.order_by(desc(PresensiIzincuti.dari))\
        .offset((page-1)*limit).limit(limit).all()
        
    data = []
    for r, nama, jenis in results:
        data.append({
            "kode_izin_cuti": r.kode_izin_cuti,
            "tanggal": str(r.tanggal),
            "dari": str(r.dari),
            "sampai": str(r.sampai),
            "kode_cuti": r.kode_cuti,
            "jenis_cuti": jenis,
            "nama_karyawan": nama,
            "keterangan": r.keterangan,
            "status": r.status
        })
        
    return {
        "status": True,
        "data": {
            "current_page": page,
            "data": data,
            "total": total
        }
    }

@router.get("/izin-cuti/{kode}")
async def detail_izin_cuti(
    kode: str,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    result = db.query(PresensiIzincuti, Karyawan.nama_karyawan, Cuti.jenis_cuti)\
        .join(Karyawan, PresensiIzincuti.nik == Karyawan.nik)\
        .join(Cuti, PresensiIzincuti.kode_cuti == Cuti.kode_cuti)\
        .filter(PresensiIzincuti.kode_izin_cuti == kode)\
        .first()
        
    if not result:
        raise HTTPException(404, "Izin cuti tidak ditemukan")
        
    r, nama, jenis = result
    
    # Flatten object for response
    # Use Pydantic or manual dict
    # Using manual dict to match generic object structure
    # SQLAlchemy object to dict?
    d = r.__dict__.copy()
    if '_sa_instance_state' in d: del d['_sa_instance_state']
    
    d['nama_karyawan'] = nama
    d['jenis_cuti'] = jenis
    
    return {"status": True, "data": d}

@router.post("/izin-cuti/store")
async def store_izin_cuti(
    dari: str = Form(...),
    sampai: str = Form(...),
    kode_cuti: str = Form(...),
    keterangan: str = Form(...),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    nik = user.nik
    d_dari = datetime.strptime(dari, "%Y-%m-%d").date()
    d_sampai = datetime.strptime(sampai, "%Y-%m-%d").date()
    
    # 1. Conflict Check
    if check_conflict(nik, d_dari, d_sampai, db):
         raise HTTPException(400, "Sudah ada pengajuan izin lain pada rentang tanggal tersebut")
         
    # 2. Generate Code: IC + YYMM + 000X
    prefix = f"IC{d_dari.strftime('%y%m')}"
    last = db.query(PresensiIzincuti).filter(PresensiIzincuti.kode_izin_cuti.like(f"{prefix}%"))\
        .order_by(desc(PresensiIzincuti.kode_izin_cuti)).first()
    last_code = last.kode_izin_cuti if last else None
    kode = buat_kode(last_code, prefix, 4)
    
    new_cuti = PresensiIzincuti(
        kode_izin_cuti=kode,
        nik=nik,
        id_user=user.id,
        kode_cuti=kode_cuti,
        tanggal=d_dari,
        dari=d_dari,
        sampai=d_sampai,
        keterangan=keterangan,
        status=0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_cuti)
    db.commit()
    
    return {"status": True, "message": "Izin cuti berhasil diajukan", "data": new_cuti}

# --- IZIN DINAS ---

@router.get("/izin-dinas")
async def list_izin_dinas(
    dari: Optional[str] = None,
    sampai: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    nik = user.nik
    query = db.query(PresensiIzindinas, Karyawan.nama_karyawan)\
        .join(Karyawan, PresensiIzindinas.nik == Karyawan.nik)\
        .filter(PresensiIzindinas.nik == nik)
        
    if dari and sampai:
         query = query.filter(PresensiIzindinas.tanggal >= dari, PresensiIzindinas.tanggal <= sampai)
         
    total = query.count()
    results = query.order_by(desc(PresensiIzindinas.tanggal))\
        .offset((page-1)*limit).limit(limit).all()
        
    data = []
    for r, nama in results:
        data.append({
            "kode_izin_dinas": r.kode_izin_dinas,
            "tanggal": str(r.tanggal),
            "dari": str(r.dari),
            "sampai": str(r.sampai),
            "keterangan": r.keterangan,
            "status": r.status,
            "nama_karyawan": nama
        })
        
    return {
        "status": True, 
        "data": {
            "current_page": page,
            "data": data,
            "total": total
        }
    }

@router.get("/izin-dinas/{kode}")
async def detail_izin_dinas(
    kode: str,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    result = db.query(PresensiIzindinas, Karyawan.nama_karyawan)\
        .join(Karyawan, PresensiIzindinas.nik == Karyawan.nik)\
        .filter(PresensiIzindinas.kode_izin_dinas == kode)\
        .first()
        
    if not result:
        raise HTTPException(404, "Izin dinas tidak ditemukan")
        
    r, nama = result
    d = r.__dict__.copy()
    if '_sa_instance_state' in d: del d['_sa_instance_state']
    d['nama_karyawan'] = nama
    
    return {"status": True, "data": d}

@router.post("/izin-dinas/store")
async def store_izin_dinas(
    dari: str = Form(...),
    sampai: str = Form(...),
    keterangan: str = Form(...),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    nik = user.nik
    d_dari = datetime.strptime(dari, "%Y-%m-%d").date()
    d_sampai = datetime.strptime(sampai, "%Y-%m-%d").date()
    
    # 1. Conflict Check (Dinas usually check same logic)
    # PHP IzinDinasApiController:
    # "CEK BENTROK IZIN" -> checks Izindinas table itself for overlapping.
    
    conflict = db.query(PresensiIzindinas).filter(
        PresensiIzindinas.nik == nik,
        or_(
            and_(PresensiIzindinas.dari <= d_sampai, PresensiIzindinas.sampai >= d_dari)
        )
    ).first()
    
    if conflict:
        raise HTTPException(422, "Anda sudah mengajukan izin dinas pada rentang tanggal tersebut")
        
    # 2. Codes: ID + YYMM + 000X
    prefix = f"ID{d_dari.strftime('%y%m')}"
    last = db.query(PresensiIzindinas).filter(PresensiIzindinas.kode_izin_dinas.like(f"{prefix}%"))\
        .order_by(desc(PresensiIzindinas.kode_izin_dinas)).first()
    last_code = last.kode_izin_dinas if last else None
    kode = buat_kode(last_code, prefix, 4)
    
    new_dinas = PresensiIzindinas(
        kode_izin_dinas=kode,
        nik=nik,
        tanggal=d_dari,
        dari=d_dari,
        sampai=d_sampai,
        keterangan=keterangan,
        status=0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_dinas)
    db.commit()
    
    return {"status": True, "message": "Izin dinas berhasil diajukan", "data": new_dinas}
