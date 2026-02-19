from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
import shutil
import os
import uuid

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import SafetyBriefings, Turlalin, SuratMasuk, SuratKeluar, Tamu, Karyawan, PengaturanUmum, Users, Cabang, Jabatan, Departemen

router = APIRouter(
    prefix="/api/android",
    tags=["Ops Legacy"],
)

STORAGE_BREIFING = "/var/www/appPatrol/storage/app/public/briefing"
STORAGE_TURLALIN = "/var/www/appPatrol/storage/app/public/turlalin"
STORAGE_SURAT = "/var/www/appPatrol/storage/app/public/surat"

os.makedirs(STORAGE_BREIFING, exist_ok=True)
os.makedirs(STORAGE_TURLALIN, exist_ok=True)
os.makedirs(STORAGE_SURAT, exist_ok=True)

# --- SAFETY BRIEFING ---

@router.post("/regu/parameter")
async def store_regu_parameter():
    return {"status": True, "message": "Regu Disimpan"}

# @router.get("/safetybriefing")
# @router.get("/safety-briefing")
# async def list_safety_briefing(
#     limit: int = 10,
#     user: CurrentUser = Depends(get_current_user_data),
#     db: Session = Depends(get_db)
# ):
#     query = db.query(SafetyBriefings).order_by(desc(SafetyBriefings.tanggal_jam)).limit(limit)
#     items = query.all()
#     
#     data = []
#     for i in items:
#         data.append({
#             "id": i.id,
#             "tanggal_jam": str(i.tanggal_jam),
#             "keterangan": i.keterangan,
#             "foto": i.foto,
#             "nik_pelapor": i.nik
#         })
#     return {"status": True, "data": data}
# 
# @router.post("/safety-briefing/store")
# async def store_safety_briefing(
#     keterangan: str = Form(...),
#     foto: UploadFile = File(...),
#     user: CurrentUser = Depends(get_current_user_data),
#     db: Session = Depends(get_db)
# ):
#     if not user.nik:
#         raise HTTPException(400, "NIK Required")
#         
#     filename = f"briefing_{uuid.uuid4().hex[:6]}.jpg"
#     path = os.path.join(STORAGE_BREIFING, filename)
#     with open(path, "wb") as buffer:
#         shutil.copyfileobj(foto.file, buffer)
#         
#     new_data = SafetyBriefings(
#         nik=user.nik,
#         keterangan=keterangan,
#         tanggal_jam=datetime.now(),
#         foto=f"briefing/{filename}"
#     )
#     db.add(new_data)
#     db.commit()
#     
#     return {"status": True, "message": "Safety Briefing Tersimpan"}


# --- TURLALIN ---

@router.get("/turlalin")
async def list_turlalin(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    items = db.query(Turlalin).order_by(desc(Turlalin.jam_masuk)).limit(limit).all()
    data = []
    for i in items:
        data.append({
            "id": i.id,
            "nomor_polisi": i.nomor_polisi,
            "jam_masuk": str(i.jam_masuk),
            "jam_keluar": str(i.jam_keluar) if i.jam_keluar else None,
            "keterangan": i.keterangan,
            "foto": i.foto
        })
    return {"status": True, "data": data}

@router.post("/turlalin/store") # Called for Masuk
async def store_turlalin_masuk(
    nomor_polisi: str = Form(...),
    keterangan: str = Form(""),
    foto: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    filename = f"turlalin_{uuid.uuid4().hex[:6]}.jpg"
    path = os.path.join(STORAGE_TURLALIN, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(foto.file, buffer)
        
    new_data = Turlalin(
        nik=user.nik,
        nomor_polisi=nomor_polisi,
        keterangan=keterangan,
        jam_masuk=datetime.now(),
        foto=f"turlalin/{filename}"
    )
    db.add(new_data)
    db.commit()
    return {"status": True, "message": "Turlalin Masuk Tercatat", "data": {"id": new_data.id}}

@router.post("/turlalin/checkout/{id}")
async def store_turlalin_keluar(
    id: int,
    foto_keluar: UploadFile = File(None), # Optional?
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    data = db.query(Turlalin).filter(Turlalin.id == id).first()
    if not data:
        raise HTTPException(404, "Data tidak ditemukan")
        
    data.jam_keluar = datetime.now()
    data.nik_keluar = user.nik
    # If foto keluar needed, handle it.
    
    db.commit()
    return {"status": True, "message": "Turlalin Keluar Tercatat"}
    

# --- SURAT MENYURAT ---
# MOVED TO app/routers/surat_legacy.py
# 
# @router.get("/surat-masuk")
# async def list_surat_masuk(limit: int=10, db: Session = Depends(get_db)):
#     items = db.query(SuratMasuk).order_by(desc(SuratMasuk.tanggal_surat)).limit(limit).all()
#     # Serialize...
#     return {"status": True, "data": []} # Implement detail if needed
# 
# @router.post("/surat-masuk/store")
# async def store_surat_masuk(
#     nomor_surat: str = Form(...),
#     asal_surat: str = Form(...),
#     tujuan_surat: str = Form(...),
#     perihal: str = Form(...),
#     foto: UploadFile = File(...),
#     user: CurrentUser = Depends(get_current_user_data),
#     db: Session = Depends(get_db)
# ):
#     filename = f"surat_masuk_{uuid.uuid4().hex[:6]}.jpg"
#     path = os.path.join(STORAGE_SURAT, filename)
#     with open(path, "wb") as buffer:
#         shutil.copyfileobj(foto.file, buffer)
#         
#     new_surat = SuratMasuk(
#         nik_satpam=user.nik,
#         nomor_surat=nomor_surat,
#         asal_surat=asal_surat,
#         tujuan_surat=tujuan_surat,
#         perihal=perihal,
#         tanggal_surat=datetime.now(),
#         foto=f"surat/{filename}",
#         status_surat='MASUK'
#     )
#     db.add(new_surat)
#     db.commit()
#     return {"status": True, "message": "Surat Masuk Tercatat"}
# 
# @router.post("/surat-keluar/store")
# async def store_surat_keluar(
#     nomor_surat: str = Form(...),
#     tujuan_surat: str = Form(...),
#     perihal: str = Form(...),
#     foto: UploadFile = File(...),
#     user: CurrentUser = Depends(get_current_user_data),
#     db: Session = Depends(get_db)
# ):
#     filename = f"surat_keluar_{uuid.uuid4().hex[:6]}.jpg"
#     path = os.path.join(STORAGE_SURAT, filename)
#     with open(path, "wb") as buffer:
#         shutil.copyfileobj(foto.file, buffer)
#         
#     new_surat = SuratKeluar(
#         nik_satpam=user.nik,
#         nomor_surat=nomor_surat,
#         tujuan_surat=tujuan_surat,
#         perihal=perihal,
#         tanggal_surat=datetime.now(),
#         foto=f"surat/{filename}",
#         status_surat='KELUAR'
#     )
#     db.add(new_surat)
#     db.commit()
#     return {"status": True, "message": "Surat Keluar Tercatat"}


# --- TAMU ---
# MOVED TO app/routers/tamu_legacy.py


# --- PENGATURAN (User Profile?) & VERSION ---

@router.get("/pengaturan")
async def get_pengaturan_android(
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    return await _get_profile_data(user, db)

@router.get("/pengaturan/profil")
async def get_profil_android(
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    return await _get_profile_data(user, db)

async def _get_profile_data(user, db):
    u = db.query(Users).filter(Users.id == user.id).first()
    if not u:
         raise HTTPException(401, "User not found")
         
    karyawan = None
    judul_cabang = "-"
    judul_jabatan = "-"
    foto_user = ""
    
    judul_departemen = "-"
    
    if user.nik:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
        if karyawan:
            foto_user = karyawan.foto or ""
            if karyawan.kode_cabang:
                c = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
                if c: judul_cabang = c.nama_cabang
            
            if karyawan.kode_jabatan:
                j = db.query(Jabatan).filter(Jabatan.kode_jabatan == karyawan.kode_jabatan).first()
                if j: judul_jabatan = j.nama_jabatan
                
            if karyawan.kode_dept:
                d = db.query(Departemen).filter(Departemen.kode_dept == karyawan.kode_dept).first()
                if d: judul_departemen = d.nama_dept
    
    # Construct Base URL for photo
    base_url = "https://frontend.k3guard.com/api-py/storage/"
    full_foto_url = f"{base_url}karyawan/{foto_user}" if foto_user and karyawan else ""
    if not full_foto_url and u.foto:
        full_foto_url = f"{base_url}users/{u.foto}"

    data_pengaturan = {
        "id": u.id,
        "nik": user.nik,
        "nama": karyawan.nama_karyawan if karyawan else u.name,
        "username": u.username,
        "email": u.email or "",
        "no_hp": karyawan.no_hp if karyawan else u.phone,
        "alamat": karyawan.alamat if karyawan else u.address,
        "no_ktp": karyawan.no_ktp if karyawan else "",
        "cabang": judul_cabang,
        "jabatan": judul_jabatan,
        "departemen": judul_departemen,
        "foto": full_foto_url,
        "foto_filename": foto_user if karyawan else u.foto, # For reference
        "created_at": str(u.created_at) if u.created_at else "",
        "updated_at": str(u.updated_at) if u.updated_at else ""
    }
    
    return {"status": "success", "data": data_pengaturan}

@router.get("/app/version-policy")
async def get_version_policy(db: Session = Depends(get_db)):
    setting = db.query(PengaturanUmum).first()
    if not setting:
        return {}
        
    return {
        "minSupportedVersionCode": setting.min_supported_version_code,
        "latestVersionCode": setting.latest_version_code,
        "updateUrl": setting.update_url,
        "message": setting.update_message
    }
