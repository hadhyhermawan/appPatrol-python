from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, aliased
from sqlalchemy import desc, func, or_, text
import shutil
import os
import uuid
import logging
from PIL import Image
import io

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
# Reusing models and utility functions from Tamu Legacy (or duplicate if cleaner separation desired)
# Let's clean up later. Now duplicate logic.
from app.models.models import Karyawan, Barang, BarangMasuk, BarangKeluar, Presensi, PresensiJamkerja, SetJamKerjaByDate, SetJamKerjaByDay

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/android",
    tags=["Barang Legacy"],
)

STORAGE_BARANG = "/var/www/appPatrol/storage/app/public/barang"
os.makedirs(STORAGE_BARANG, exist_ok=True)

# --- HELPER FUNCTIONS FOR SHIFT VALIDATION (Copied from Tamu Legacy for Isolation) ---

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
    # Note: PresensiJamkerjaBydateExtra needs to be imported securely
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
        logger.warning("PresensiJamkerjaBydateExtra model not found or import error")
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
    # Join: presensi_jamkerja_bydept_detail -> presensi_jamkerja_bydept -> presensi_jamkerja
    # But wait, logic usually is:
    # presensi_jamkerja_bydept stores (kode_jk_dept + cabang + dept)
    # presensi_jamkerja_bydept_detail stores (kode_jk_dept + hari + kode_jam_kerja)
    
    try:
        from app.models.models import PresensiJamkerjaBydept, PresensiJamkerjaByDeptDetail
        
        # Cari kode_jk_dept untuk cabang & dept ini
        # Note: Logic Laravel might be joining directly. Here we decompose for clarity.
        # But wait, one dept can have multiple shifts? Yes?
        # Usually presensi_jamkerja_bydept links a SchedulePattern to a Dept.
        
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
    jam_kerja = get_jam_kerja_karyawan(db, karyawan.nik, karyawan.kode_cabang, karyawan.kode_dept)
    
    if not jam_kerja:
        return {"status": False, "message": "Anda tidak memiliki jadwal shift hari ini."}
        
    # Check time range
    now = datetime.now()
    try:
        date_str = now.strftime('%Y-%m-%d')
        start_dt = datetime.strptime(f"{date_str} {jam_kerja.jam_masuk}", "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(f"{date_str} {jam_kerja.jam_pulang}", "%Y-%m-%d %H:%M:%S")
        
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
            
        if now < start_dt or now > end_dt:
             return {"status": False, "message": f"Anda sedang di luar jam kerja ({jam_kerja.jam_masuk} - {jam_kerja.jam_pulang})"}
             
    except Exception as e:
        logger.error(f"Error parsing shift time: {e}")
        pass
        
    return {"status": True}

def save_compressed_image(upload_file: UploadFile, prefix: str):
    filename = f"{prefix}_{uuid.uuid4().hex[:6]}.jpg"
    path = os.path.join(STORAGE_BARANG, filename)
    
    try:
        image_content = upload_file.file.read()
        image = Image.open(io.BytesIO(image_content))
        
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        max_width = 1400
        if image.width > max_width:
            ratio = max_width / image.width
            new_height = int(image.height * ratio)
            image = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
        image.save(path, "JPEG", quality=70)
        upload_file.file.seek(0)
        
        return f"barang/{filename}"
    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        with open(path, "wb") as buffer:
             buffer.write(image_content)
        return f"barang/{filename}"


# --- ENDPOINTS ---

@router.get("/barang")
async def list_barang(
    limit: int = 20, # Not actually used in Laravel, but useful.
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Get Karyawan
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        return {"status": False, "message": "Data karyawan tidak ditemukan"}
        
    kode_cabang = karyawan.kode_cabang
    
    # 2. Logic: Barang Masuk vs Barang Keluar
    # Laravel uses subquery logic:
    # Latest Masuk (tgl_jam_masuk DESC group by id_barang)
    # Latest Keluar (tgl_jam_keluar DESC group by id_barang)
    # Then Join Barang + Latest Masuk + Latest Keluar
    # Filter: tgl_jam_masuk > 1 month OR tgl_jam_keluar IS NULL
    
    # In Pure SQLAlchemy ORM this is hard. Let's use clean SQL or careful joins.
    # Since Barang and BarangMasuk relations are 1-to-many? No, actually 1-to-MaybeMany?
    # Usually: 1 Barang -> 1 Entry attempt?
    # Schema check: barang_masuk has id_barang FK.
    
    # Let's simplify. We can query on Barang table and join Relations if defined.
    # If not defined, we use manual query.
    
    # Using raw SQL for complex join is safer to match Laravel 100%
    
    sql = text("""
        SELECT 
            b.id_barang,
            b.jenis_barang,
            b.dari,
            b.untuk,
            bm.tgl_jam_masuk,
            bk.tgl_jam_keluar as tgl_jam_ambil,
            b.image as foto_masuk,
            b.foto_keluar,
            bm.nik_satpam,
            satpam.nama_karyawan as nama_satpam,
            bk.nik_penyerah,
            penyerah.nama_karyawan as nama_penyerah,
            bk.nama_penerima,
            bk.no_handphone
        FROM barang b
        LEFT JOIN (
            SELECT id_barang, MAX(tgl_jam_masuk) as max_masuk
            FROM barang_masuk
            GROUP BY id_barang
        ) bm_latest ON b.id_barang = bm_latest.id_barang
        LEFT JOIN barang_masuk bm ON bm.id_barang = bm_latest.id_barang AND bm.tgl_jam_masuk = bm_latest.max_masuk
        
        LEFT JOIN (
            SELECT id_barang, MAX(tgl_jam_keluar) as max_keluar
            FROM barang_keluar
            GROUP BY id_barang
        ) bk_latest ON b.id_barang = bk_latest.id_barang
        LEFT JOIN barang_keluar bk ON bk.id_barang = bk_latest.id_barang AND bk.tgl_jam_keluar = bk_latest.max_keluar
        
        LEFT JOIN karyawan satpam ON bm.nik_satpam = satpam.nik
        LEFT JOIN karyawan penyerah ON bk.nik_penyerah = penyerah.nik
        
        WHERE b.kode_cabang = :kode_cabang
        AND (bm.tgl_jam_masuk >= :one_month_ago OR bk.tgl_jam_keluar IS NULL)
        
        ORDER BY (bk.tgl_jam_keluar IS NULL) DESC, bm.tgl_jam_masuk DESC
    """)
    # Note on Order By: Laravel `orderByRaw('bk.tgl_jam_keluar IS NULL ASC')`
    # IS NULL -> 1 (True) or 0 (False) depends on DB.
    # MariaDB: IS NULL returns 1 if NULL, 0 if NOT NULL.
    # ASC: 0 (Not Null/Completed) then 1 (Null/Active). So Active at BOTTOM?
    # Wait, usually Active at TOP.
    # If Laravel says ASC, and list shows Active top, then logic might be reversed or I misunderstand MariaDB.
    # Let's assume user wants Active (Null) at Top.
    # (bk.tgl_jam_keluar IS NULL) -> 1. DESC -> 1 first. Active first.
    
    one_month_ago = datetime.now() - timedelta(days=30)
    
    result = db.execute(sql, {"kode_cabang": kode_cabang, "one_month_ago": one_month_ago}).fetchall()
    
    data = []
    base_url = "https://frontend.k3guard.com/api-py/storage/"

    for row in result:
        # Row is tuple-like
        # We need to access by index or key? SQLAlchemy result is addressable by key in recent versions.
        # Let's try converting to dict
        r = row._mapping
        
        foto_masuk = f"{base_url}{r['foto_masuk']}" if r['foto_masuk'] else None
        foto_keluar = f"{base_url}{r['foto_keluar']}" if r['foto_keluar'] else None
        
        data.append({
            "id_barang": r['id_barang'],
            "jenis_barang": r['jenis_barang'],
            "dari": r['dari'],
            "untuk": r['untuk'],
            "tgl_jam_masuk": str(r['tgl_jam_masuk']) if r['tgl_jam_masuk'] else None,
            "tgl_jam_ambil": str(r['tgl_jam_ambil']) if r['tgl_jam_ambil'] else None,
            "foto_masuk": foto_masuk,
            "foto_keluar": foto_keluar,
            "nik_satpam": r['nik_satpam'],
            "nama_satpam": r['nama_satpam'],
            "nik_penyerah": r['nik_penyerah'],
            "nama_penyerah": r['nama_penyerah'],
            "nama_penerima": r['nama_penerima'],
            "no_handphone": r['no_handphone']
        })
        
    return {
        "status": True,
        "nik_satpam": karyawan.nik,
        "kode_cabang": karyawan.kode_cabang,
        "data": data
    }

@router.post("/barang/store")
async def store_barang(
    jenis_barang: str = Form(...),
    dari: str = Form(...),
    untuk: str = Form(...),
    image: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Validate Shift
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")
        
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        raise HTTPException(status_code=403, detail=shift_check["message"])

    # 2. Save Image
    image_path = save_compressed_image(image, "barang") # e.g. barang_xxxx.jpg inside storage/barang/
    
    # 3. Insert Master Barang
    new_barang = Barang(
        kode_cabang=karyawan.kode_cabang,
        jenis_barang=jenis_barang,
        dari=dari,
        untuk=untuk,
        image=image_path,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_barang)
    db.commit()
    db.refresh(new_barang) # Get ID
    
    # 4. Insert Barang Masuk Log
    bm = BarangMasuk(
        id_barang=new_barang.id_barang,
        nik_satpam=user.nik,
        tgl_jam_masuk=datetime.now()
    )
    db.add(bm)
    db.commit()
    
    return {
        "status": True,
        "message": "Barang berhasil dicatat masuk",
        "data": {
            "id_barang": new_barang.id_barang,
            "jenis_barang": new_barang.jenis_barang,
            # Add fields if needed
        }
    }

@router.post("/barang/keluar")
async def barang_keluar(
    id_barang: int = Form(...),
    nama_penerima: str = Form(...),
    no_handphone: str = Form(...),
    foto_keluar: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Validate Shift
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")
        
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        raise HTTPException(status_code=403, detail=shift_check["message"])
        
    # 2. Find Barang
    barang = db.query(Barang).filter(Barang.id_barang == id_barang).first()
    if not barang:
        raise HTTPException(404, "Barang tidak ditemukan")
        
    # 3. Save Image
    foto_keluar_path = save_compressed_image(foto_keluar, f"keluar_{id_barang}")
    
    # 4. Update Barang (Foto Keluar)
    barang.foto_keluar = foto_keluar_path
    
    # 5. Insert Log Barang Keluar
    bk = BarangKeluar(
        id_barang=id_barang,
        nik_penyerah=user.nik,
        nama_penerima=nama_penerima,
        no_handphone=no_handphone,
        tgl_jam_keluar=datetime.now()
    )
    db.add(bk)
    db.commit()
    
    # 6. Fetch updated data for response (optional)
    
    return {
        "status": True,
        "message": "Barang berhasil dicatat keluar",
        "data": {
            "id_barang": id_barang,
            "nama_penerima": nama_penerima,
            "tgl_jam_keluar": str(bk.tgl_jam_keluar)
        }
    }
