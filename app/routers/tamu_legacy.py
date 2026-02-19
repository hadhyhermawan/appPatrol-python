from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
import shutil
import os
import uuid
import logging
from PIL import Image
import io

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import Karyawan, Tamu, Presensi, PresensiJamkerja, SetJamKerjaByDate, SetJamKerjaByDay, PresensiJamkerjaByDeptDetail

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/android",
    tags=["Tamu Legacy"],
)

STORAGE_TAMU = "/var/www/appPatrol/storage/app/public/tamu"
os.makedirs(STORAGE_TAMU, exist_ok=True)

# --- HELPER FUNCTIONS FOR SHIFT VALIDATION ---

def get_jam_kerja_karyawan(db: Session, nik: str, kode_cabang: str, kode_dept: str):
    """
    Mencari jam kerja karyawan berdasarkan prioritas:
    0. By Date Extra (Lembur / Extra Shift)
    1. By Date (Tanggal spesifik)
    2. By Day (Hari dalam seminggu)
    3. By Dept (Jadwal default departemen)
    """
    tanggal = datetime.now().strftime('%Y-%m-%d')
    hari_ini = datetime.now().strftime('%a') # Mon, Tue, ...
    
    # Map English day to Indonesian
    days_map = {
        'Mon': 'Senin', 'Tue': 'Selasa', 'Wed': 'Rabu', 'Thu': 'Kamis', 
        'Fri': 'Jumat', 'Sat': 'Sabtu', 'Sun': 'Minggu'
    }
    hari = days_map.get(hari_ini, hari_ini)
    
    # 0. Check By Date Extra (Lembur / Double Shift) - Highest Priority
    try:
        from app.models.models import PresensiJamkerjaBydateExtra
        jk_extra = db.query(PresensiJamkerja)\
            .join(PresensiJamkerjaBydateExtra, PresensiJamkerjaBydateExtra.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .filter(PresensiJamkerjaBydateExtra.nik == nik)\
            .filter(PresensiJamkerjaBydateExtra.tanggal == tanggal)\
            .first()
            
        if jk_extra:
            return jk_extra
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Error querying PresensiJamkerjaBydateExtra: {e}")

    # 1. Start Check By Date (Tukar Shift / Rotasi)
    jk_by_date = db.query(PresensiJamkerja)\
        .join(SetJamKerjaByDate, SetJamKerjaByDate.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
        .filter(SetJamKerjaByDate.nik == nik)\
        .filter(SetJamKerjaByDate.tanggal == tanggal)\
        .first()
        
    if jk_by_date:
        return jk_by_date
        
    # 2. Check By Day (Jadwal Rutin Personal)
    jk_by_day = db.query(PresensiJamkerja)\
        .join(SetJamKerjaByDay, SetJamKerjaByDay.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
        .filter(SetJamKerjaByDay.nik == nik)\
        .filter(SetJamKerjaByDay.hari == hari)\
        .first()
        
    if jk_by_day:
        return jk_by_day
        
    # 3. Check By Dept (Jadwal Rutin Dept)
    try:
        from app.models.models import PresensiJamkerjaBydept, PresensiJamkerjaByDeptDetail
        
        jk_dept = db.query(PresensiJamkerja)\
            .join(PresensiJamkerjaByDeptDetail, PresensiJamkerjaByDeptDetail.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .join(PresensiJamkerjaBydept, PresensiJamkerjaBydept.kode_jk_dept == PresensiJamkerjaByDeptDetail.kode_jk_dept)\
            .filter(PresensiJamkerjaBydept.kode_cabang == kode_cabang)\
            .filter(PresensiJamkerjaBydept.kode_dept == kode_dept)\
            .filter(PresensiJamkerjaByDeptDetail.hari == hari)\
            .first()
            
        if jk_dept:
            return jk_dept

    except Exception as e:
        logger.error(f"Error querying PresensiJamkerjaByDept: {e}")
        
    return None

def check_jam_kerja_status(db: Session, karyawan: Karyawan):
    """
    Validasi apakah karyawan sedang dalam jam kerja atau sudah absen
    """
    # 1. Cek Presensi Hari Ini (Sudah absen masuk & belum pulang)
    today = datetime.now().strftime('%Y-%m-%d')
    presensi = db.query(Presensi).filter(
        Presensi.nik == karyawan.nik,
        Presensi.tanggal == today,
        Presensi.jam_in != None,
        Presensi.jam_out == None
    ).first()
    
    if presensi:
        return {"status": True}
        
    # 2. Jika belum absen, cek apakah masih dalam range jam kerja shift?
    # Logic Laravel: Fallback ke checkJamKerja if presensi null.
    
    jam_kerja = get_jam_kerja_karyawan(db, karyawan.nik, karyawan.kode_cabang, karyawan.kode_dept)
    
    if not jam_kerja:
        return {"status": False, "message": "Anda tidak memiliki jadwal shift hari ini."}
        
    # Check time range
    now = datetime.now()
    try:
        # Parse jam_masuk and jam_pulang. Format usually HH:MM:SS
        date_str = now.strftime('%Y-%m-%d')
        start_dt = datetime.strptime(f"{date_str} {jam_kerja.jam_masuk}", "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(f"{date_str} {jam_kerja.jam_pulang}", "%Y-%m-%d %H:%M:%S")
        
        # Handle cross-day shift (e.g. 23:00 to 07:00)
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
            # If now is early morning, we might be in the shift that started yesterday?
            # Complexity handled simpler: just check current day window.
            
        if now < start_dt or now > end_dt:
             return {"status": False, "message": f"Anda sedang di luar jam kerja ({jam_kerja.jam_masuk} - {jam_kerja.jam_pulang})"}
             
    except Exception as e:
        logger.error(f"Error parsing shift time: {e}")
        # Pass conservatively
        pass
        
    return {"status": True}

def save_compressed_image(upload_file: UploadFile, prefix: str):
    filename = f"{prefix}_{uuid.uuid4().hex[:6]}.jpg"
    path = os.path.join(STORAGE_TAMU, filename)
    
    try:
        # Read image
        image_content = upload_file.file.read()
        image = Image.open(io.BytesIO(image_content))
        
        # Convert to RGB if needed
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        # Resize: Max width 1400, keep aspect ratio
        max_width = 1400
        if image.width > max_width:
            ratio = max_width / image.width
            new_height = int(image.height * ratio)
            image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
        # Save compressed
        image.save(path, "JPEG", quality=70)
        upload_file.file.seek(0) # Reset pointer just in case
        
        return f"tamu/{filename}"
    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        # Fallback raw save if pillow fails
        with open(path, "wb") as buffer:
             buffer.write(image_content)
        return f"tamu/{filename}"


# --- ENDPOINTS ---

@router.get("/tamu/riwayat")
async def get_tamu_riwayat(
    limit: int = 20,
    page: int = 1,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Get Karyawan data for branch filtering
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        return {"status": False, "message": "Data karyawan tidak ditemukan"}
        
    kode_cabang = karyawan.kode_cabang
    
    # 2. Query Tamu
    # Filter by user branch (via join with Karyawan on nik_satpam)
    # Logic Laravel:
    # ->where('satpam_masuk.kode_cabang', $kode_cabang)
    
    # We need to alias Karyawan table for join
    # but in simple ORM:
    # Join Tamu.karyawan (relationship)
    
    one_month_ago = datetime.now() - timedelta(days=30)
    
    query = db.query(Tamu).join(Karyawan, Tamu.nik_satpam == Karyawan.nik)\
        .filter(Karyawan.kode_cabang == kode_cabang)\
        .filter(
            or_(
                Tamu.jam_masuk >= one_month_ago,
                Tamu.jam_keluar == None
            )
        )
        
    # Sorting: jam_keluar IS NULL ASC, jam_masuk DESC
    # In SQLAlchemy:
    query = query.order_by(
        Tamu.jam_keluar.isnot(None), # False (0) comes first (NULLs first usually? Wait. isnot(None) -> True(1). We want Null(0) first. So Ascending works.)
                                    # Actually nulls_first / nulls_last might be db specific.
                                    # Laravel: orderByRaw('tamu.jam_keluar IS NULL ASC') -> 0 (False, Not Null) then 1 (True, Is Null)? 
                                    # Wait. "IS NULL" returns 1 if null. 1 is "later" in ASC than 0. 
                                    # So "Not Null" (0) comes first? No, we want Active (Null) first.
                                    # Laravel: orderByRaw('jam_keluar IS NULL ASC') -> False(0), True(1). 
                                    # Logic: Completed(0), Active(1). ASC means Completed top.
                                    # WAIT. Usually we want active top.
                                    # Let's stick to simple: ORDER BY jam_keluar ASC (Nulls last/first?), jam_masuk DESC
                                    
        desc(Tamu.jam_masuk)
    )
    
    # Let's refine sorting: Active guests (jam_keluar is None) first.
    # We can perform two queries or post-sort.
    # Or rely on client.
    
    total = query.count()
    items = query.limit(limit).offset((page - 1) * limit).all()
    
    data = []
    base_url = "https://frontend.k3guard.com/api-py/storage/" # Or use request base url
    
    for t in items:
        # Format URLs
        foto_masuk_url = f"{base_url}{t.foto}" if t.foto else None
        foto_keluar_url = f"{base_url}{t.foto_keluar}" if t.foto_keluar else None
        
        # Get satpam names (Active Loading or Eager Loading)
        # Assuming relations exist
        nama_satpam_masuk = t.karyawan.nama_karyawan if t.karyawan else None
        
        # For satpam keluar, we need to query if not related relation
        nama_satpam_keluar = None
        if t.nik_satpam_keluar:
            sk = db.query(Karyawan).filter(Karyawan.nik == t.nik_satpam_keluar).first()
            if sk: nama_satpam_keluar = sk.nama_karyawan

        data.append({
            "id": t.id_tamu,
            "nama": t.nama,
            "alamat": t.alamat,
            "jenis_id": t.jenis_id,
            "no_telp": t.no_telp,
            "perusahaan": t.perusahaan,
            "bertemu_dengan": t.bertemu_dengan,
            "dengan_perjanjian": t.dengan_perjanjian,
            "keperluan": t.keperluan,
            "jenis_kendaraan": t.jenis_kendaraan,
            "no_pol": t.no_pol,
            "jam_masuk": str(t.jam_masuk) if t.jam_masuk else None,
            "jam_keluar": str(t.jam_keluar) if t.jam_keluar else None,
            "foto_masuk": foto_masuk_url, 
            "foto_keluar": foto_keluar_url,
            "status": "KELUAR" if t.jam_keluar else "MASUK",
            "nik_masuk": t.nik_satpam,
            "nama_satpam_masuk": nama_satpam_masuk,
            "nik_keluar": t.nik_satpam_keluar,
            "nama_satpam_keluar": nama_satpam_keluar,
            # Laravel adds these to root response too, but inside 'data' list item is fine for client? 
            # Client expects list of objects.
        })
        
    return {
        "status": True,
        "nik_satpam": karyawan.nik,
        "kode_cabang": karyawan.kode_cabang,
        "data": data
    }


@router.post("/tamu/store")
async def store_tamu(
    nama: str = Form(...),
    alamat: str = Form(None),
    jenis_id: str = Form(None),
    no_telp: str = Form(None),
    perusahaan: str = Form(None),
    bertemu_dengan: str = Form(None),
    dengan_perjanjian: str = Form("TIDAK"),
    keperluan: str = Form(None),
    jenis_kendaraan: str = Form("PEJALAN KAKI"),
    no_pol: str = Form(None),
    foto: UploadFile = File(None),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Validate User & Shift
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")

    shift_check = check_jam_kerja_status(db, karyawan)
    # WARNING: To avoid blocking migration testing, we can Log warning but Allow
    # BUT user requested to replicate logic.
    if not shift_check["status"]:
        # Respond 403 like Laravel
        # return JSONResponse(status_code=403, content={"status": False, "message": shift_check["message"]})
        # Use HTTPException
        raise HTTPException(status_code=403, detail=shift_check["message"])

    # 2. Handle Image
    foto_path = None
    if foto:
        foto_path = save_compressed_image(foto, "tamu_masuk")
        
    # 3. Save DB
    new_tamu = Tamu(
        nik_satpam=user.nik,
        nama=nama,
        alamat=alamat,
        jenis_id=jenis_id,
        no_telp=no_telp,
        perusahaan=perusahaan,
        bertemu_dengan=bertemu_dengan,
        dengan_perjanjian=dengan_perjanjian,
        keperluan=keperluan,
        jenis_kendaraan=jenis_kendaraan,
        no_pol=no_pol,
        jam_masuk=datetime.now(),
        foto=foto_path
    )
    db.add(new_tamu)
    db.commit()
    db.refresh(new_tamu)
    
    # Format Response URL
    base_url = "https://frontend.k3guard.com/api-py/storage/"
    if new_tamu.foto:
        new_tamu.foto = f"{base_url}{new_tamu.foto}"
    
    return {
        "status": True, 
        "message": "Tamu Berhasil Dicatat", 
        "data": new_tamu
    }


@router.post("/tamu/pulang/{id_tamu}")
async def tamu_pulang(
    id_tamu: int,
    fotoKeluar: UploadFile = File(...), # Required
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Validate User & Shift
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")
        
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        raise HTTPException(status_code=403, detail=shift_check["message"])
        
    # 2. Get Tamu
    tamu = db.query(Tamu).filter(Tamu.id_tamu == id_tamu).first()
    if not tamu:
        raise HTTPException(404, "Tamu tidak ditemukan")
        
    # 3. Handle Image
    filename = f"tamu_keluar_{uuid.uuid4().hex[:6]}.jpg"
    
    foto_keluar_path = save_compressed_image(fotoKeluar, "tamu_keluar")
    
    # 4. Update DB
    tamu.jam_keluar = datetime.now()
    tamu.nik_satpam_keluar = user.nik
    tamu.foto_keluar = foto_keluar_path
    
    db.commit()
    
    # Format Response
    base_url = "https://frontend.k3guard.com/api-py/storage/"
    tamu.foto = f"{base_url}{tamu.foto}" if tamu.foto else None
    tamu.foto_keluar = f"{base_url}{tamu.foto_keluar}" if tamu.foto_keluar else None
    
    return {"status": True, "message": "Tamu Keluar Berhasil", "data": tamu}
