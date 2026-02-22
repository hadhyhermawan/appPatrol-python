from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
import pytz

WIB = pytz.timezone('Asia/Jakarta')
from sqlalchemy.orm import Session
from sqlalchemy import desc
import shutil
import os
import uuid
from PIL import Image
import io

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import SafetyBriefings, Turlalin, SuratMasuk, SuratKeluar, Tamu, Karyawan, Userkaryawan, PengaturanUmum, Users, Cabang, Jabatan, Departemen

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
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        return {"status": True, "message": shift_check["message"], "data": []}

    kode_cabang = karyawan.kode_cabang

    items = db.query(Turlalin).join(Karyawan, Turlalin.nik == Karyawan.nik)\
        .filter(Karyawan.kode_cabang == kode_cabang)\
        .order_by(Turlalin.jam_keluar.isnot(None), desc(Turlalin.jam_masuk)).limit(limit).all()

    base_url = "https://frontend.k3guard.com/api-py/storage/"
    data = []
    for i in items:
        foto_url = None
        if i.foto:
            foto_url = i.foto if i.foto.startswith("http") else f"{base_url}{i.foto}"
            
        foto_keluar_url = None
        if i.foto_keluar:
            foto_keluar_url = i.foto_keluar if i.foto_keluar.startswith("http") else f"{base_url}{i.foto_keluar}"

        data.append({
            "id": i.id,
            "nomor_polisi": i.nomor_polisi,
            "keterangan": i.keterangan,
            "foto": foto_url,
            "foto_keluar": foto_keluar_url,
            "jam_masuk": str(i.jam_masuk),
            "jam_keluar": str(i.jam_keluar) if i.jam_keluar else None,
            "nik": i.nik,
            "nik_keluar": i.nik_keluar,
            "nama_satpam_masuk": i.karyawan.nama_karyawan if i.karyawan else None,
            "nama_satpam_keluar": i.karyawan_.nama_karyawan if i.karyawan_ else None,
            "created_at": str(i.created_at) if hasattr(i, 'created_at') and i.created_at else None,
            "updated_at": str(i.created_at) if hasattr(i, 'updated_at') and i.updated_at else None
        })
    return {
        "status": True, 
        "nik_satpam": karyawan.nik,
        "kode_cabang": karyawan.kode_cabang,
        "data": data
    }

@router.post("/turlalin/store")
async def store_turlalin_masuk(
    nomor_polisi: str = Form(...),
    keterangan: str = Form(""),
    foto: UploadFile = File(...),
    jam_masuk: Optional[str] = Form(None),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={"status": False, "message": shift_check["message"]})

    filename = f"turlalin_{uuid.uuid4().hex[:6]}.jpg"
    path = os.path.join(STORAGE_TURLALIN, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(foto.file, buffer)
        
    # Force use server timestamp (Enterprise Optimization Step 3.1)
    # Merely logging client's time, but overriding it
    client_jam_masuk = jam_masuk
    jam_masuk_wib = datetime.now(WIB).replace(tzinfo=None)
        
    new_data = Turlalin(
        nik=user.nik,
        nomor_polisi=nomor_polisi,
        keterangan=keterangan,
        jam_masuk=jam_masuk_wib,
        foto=f"turlalin/{filename}"
    )
    db.add(new_data)
    db.commit()
    db.refresh(new_data)

    base_url = "https://frontend.k3guard.com/api-py/storage/"

    return {
        "status": True, 
        "message": "Turlalin Masuk Tercatat", 
        "data": {
            "id": new_data.id,
            "nomor_polisi": new_data.nomor_polisi,
            "keterangan": new_data.keterangan,
            "foto": f"{base_url}{new_data.foto}",
            "foto_keluar": None,
            "jam_masuk": str(new_data.jam_masuk),
            "jam_keluar": None,
            "nik": getattr(new_data, 'nik', None),
            "nik_keluar": None,
            "created_at": str(new_data.created_at) if hasattr(new_data, 'created_at') and new_data.created_at else None,
            "updated_at": str(new_data.created_at) if hasattr(new_data, 'updated_at') and new_data.updated_at else None
        }
    }

@router.post("/turlalin/keluar")
async def store_turlalin_keluar(
    id: int = Form(...),
    foto_keluar: UploadFile = File(None),
    jam_keluar: Optional[str] = Form(None),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={"status": False, "message": shift_check["message"]})

    data = db.query(Turlalin).filter(Turlalin.id == id).first()
    if not data:
        raise HTTPException(404, "Data tidak ditemukan")
        
    if foto_keluar:
        filename = f"turlalin_keluar_{uuid.uuid4().hex[:6]}.jpg"
        path = os.path.join(STORAGE_TURLALIN, filename)
        with open(path, "wb") as buffer:
            shutil.copyfileobj(foto_keluar.file, buffer)
        data.foto_keluar = f"turlalin/{filename}"
        
    # Force use server timestamp (Enterprise Optimization Step 3.1)
    client_jam_keluar = jam_keluar
    jam_keluar_wib = datetime.now(WIB).replace(tzinfo=None)
        
    data.jam_keluar = jam_keluar_wib
    data.nik_keluar = user.nik
    
    db.commit()
    db.refresh(data)

    base_url = "https://frontend.k3guard.com/api-py/storage/"
    foto_url = data.foto if data.foto and data.foto.startswith("http") else f"{base_url}{data.foto}" if data.foto else None
    foto_keluar_url = data.foto_keluar if data.foto_keluar and data.foto_keluar.startswith("http") else f"{base_url}{data.foto_keluar}" if data.foto_keluar else None

    return {
        "status": True, 
        "message": "Turlalin Keluar Tercatat",
        "data": {
            "id": data.id,
            "nomor_polisi": data.nomor_polisi,
            "keterangan": data.keterangan,
            "foto": foto_url,
            "foto_keluar": foto_keluar_url,
            "jam_masuk": str(data.jam_masuk),
            "jam_keluar": str(data.jam_keluar) if data.jam_keluar else None,
            "nik": data.nik,
            "nik_keluar": data.nik_keluar,
            "nama_satpam_masuk": data.karyawan.nama_karyawan if data.karyawan else None,
            "nama_satpam_keluar": data.karyawan_.nama_karyawan if hasattr(data, 'karyawan_') and data.karyawan_ else None,
            "created_at": str(data.created_at) if hasattr(data, 'created_at') and data.created_at else None,
            "updated_at": str(data.created_at) if hasattr(data, 'updated_at') and data.updated_at else None
        }
    }
    

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

@router.post("/pengaturan/updatefotoprofil")
async def update_foto_profil(
    foto: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    """Update foto profil karyawan"""
    u = db.query(Users).filter(Users.id == user.id).first()
    if not u:
        raise HTTPException(401, "User tidak ditemukan")

    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == user.id).first()
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first() if user_karyawan else None

    # Compress & save image
    base_url = "https://frontend.k3guard.com/api-py/storage/"
    try:
        image_content = await foto.read()
        image = Image.open(io.BytesIO(image_content))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        # Resize jika terlalu besar
        max_w = 800
        if image.width > max_w:
            ratio = max_w / image.width
            image = image.resize((max_w, int(image.height * ratio)), Image.Resampling.LANCZOS)

        filename = f"foto_{uuid.uuid4().hex[:8]}.jpg"
        if karyawan:
            save_dir = f"/var/www/appPatrol/storage/app/public/karyawan"
            rel_path = f"karyawan/{filename}"
        else:
            save_dir = f"/var/www/appPatrol/storage/app/public/users"
            rel_path = f"users/{filename}"

        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, filename)
        image.save(path, "JPEG", quality=80)

    except Exception as e:
        raise HTTPException(500, f"Gagal memproses foto: {str(e)}")

    # Update record
    if karyawan:
        karyawan.foto = filename
    else:
        u.foto = filename

    db.commit()

    foto_url = f"{base_url}{rel_path}"
    nama = karyawan.nama_karyawan if karyawan else u.name
    nik = user_karyawan.nik if user_karyawan else ""

    return {
        "status": True,
        "message": "Foto profil berhasil diperbarui",
        "data": {
            "nik": nik,
            "nama_karyawan": nama,
            "foto": foto_url
        }
    }

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
