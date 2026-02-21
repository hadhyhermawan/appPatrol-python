from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime, date, timedelta, timezone
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

# Timezone WIB (UTC+7)
WIB = timezone(timedelta(hours=7))

def now_wib() -> datetime:
    """Waktu sekarang dalam WIB (UTC+7), tanpa info timezone (naive) untuk kompatibilitas DB."""
    return datetime.now(WIB).replace(tzinfo=None)

# --- HELPER FUNCTIONS FOR SHIFT VALIDATION ---

def get_jam_kerja_karyawan(db: Session, nik: str, kode_cabang: str, kode_dept: str):
    """
    Mencari jam kerja karyawan berdasarkan prioritas:
    0. By Date Extra (Lembur / Extra Shift)
    1. By Date (Tanggal spesifik)
    2. By Day (Hari dalam seminggu)
    3. By Dept (Jadwal default departemen)
    """
    tanggal = now_wib().strftime('%Y-%m-%d')
    hari_ini = now_wib().strftime('%a') # Mon, Tue, ...
    
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
    Validasi ketat: karyawan HARUS memiliki shift, HARUS sudah absen masuk, BELUM absen pulang,
    dan HARUS berada di dalam rentang waktu jam kerjanya.
    """
    today = now_wib().strftime('%Y-%m-%d')
    yesterday = (now_wib() - timedelta(days=1)).strftime('%Y-%m-%d')

    # 1. Cek Presensi Hari Ini
    presensi = db.query(Presensi).filter(
        Presensi.nik == karyawan.nik,
        Presensi.tanggal == today,
        Presensi.jam_in != None,
        Presensi.jam_out == None
    ).first()

    # 1b. Cek Lintas Hari (Shift mulai kemarin, belum pulang)
    if not presensi:
        presensi = db.query(Presensi).filter(
            Presensi.nik == karyawan.nik,
            Presensi.tanggal == yesterday,
            Presensi.lintashari == 1,
            Presensi.jam_in != None,
            Presensi.jam_out == None
        ).first()

    if not presensi:
        return {"status": False, "message": "Anda belum absen masuk atau sudah absen pulang."}

    # 2. Cek jadwal shift
    jam_kerja = get_jam_kerja_karyawan(db, karyawan.nik, karyawan.kode_cabang, karyawan.kode_dept)

    if not jam_kerja:
        return {"status": False, "message": "Anda tidak memiliki jadwal kerja hari ini."}

    # 3. Cek window waktu
    now = now_wib()
    try:
        presensi_date = str(presensi.tanggal)
        start_dt = datetime.strptime(f"{presensi_date} {jam_kerja.jam_masuk}", "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(f"{presensi_date} {jam_kerja.jam_pulang}", "%Y-%m-%d %H:%M:%S")

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        if now < start_dt or now > end_dt:
            jam_masuk = str(jam_kerja.jam_masuk)[:5]   # HH:MM
            jam_pulang = str(jam_kerja.jam_pulang)[:5]  # HH:MM
            return {"status": False, "message": f"Di luar jam kerja shift {jam_masuk}–{jam_pulang}."}

    except Exception as e:
        logger.error(f"Error parsing shift time: {e}")
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

    # Cek shift (hanya untuk info, TIDAK memblokir tampilan data)
    shift_check = check_jam_kerja_status(db, karyawan)
    shift_aktif = shift_check["status"]

    kode_cabang = karyawan.kode_cabang
    nik = karyawan.nik

    # Gunakan now_wib() — selalu WIB terlepas dari timezone server
    now_local = now_wib()
    thirty_days_ago = now_local - timedelta(days=30)

    logger.info(f"[TamuRiwayat] NIK={nik} kode_cabang={kode_cabang} shift_aktif={shift_aktif} range=30hari")

    # 2. Build base query berdasarkan cabang karyawan
    from sqlalchemy.orm import aliased
    KaryawanSatpam = aliased(Karyawan)

    if kode_cabang:
        base_q = db.query(Tamu)\
            .join(KaryawanSatpam, Tamu.nik_satpam == KaryawanSatpam.nik)\
            .filter(KaryawanSatpam.kode_cabang == kode_cabang)
    else:
        # Fallback: tampilkan tamu yg dicatat oleh karyawan ini saja
        base_q = db.query(Tamu).filter(Tamu.nik_satpam == nik)

    # 3. Filter: tamu 30 hari terakhir ATAU yang belum pulang (jam_keluar = NULL)
    base_q = base_q.filter(
        or_(
            Tamu.jam_masuk >= thirty_days_ago,  # 30 hari terakhir
            Tamu.jam_keluar == None              # belum pulang (selalu tampilkan)
        )
    )

    # 4. Sorting: belum pulang (NULL) dulu di atas, lalu masuk terbaru
    base_q = base_q.order_by(
        Tamu.jam_keluar.isnot(None),  # NULL = False = naik duluan
        desc(Tamu.jam_masuk)
    )

    total = base_q.count()
    items = base_q.limit(limit).offset((page - 1) * limit).all()

    logger.info(f"[TamuRiwayat] total_query={total} returned={len(items)}")

    # 5. Build response
    STORAGE_BASE = "https://frontend.k3guard.com/api-py/storage/"

    def _build_foto_url(path: str):
        if not path:
            return None
        if path.startswith(("http://", "https://")):
            return path
        return f"{STORAGE_BASE}{path}"

    data = []
    for t in items:
        nama_satpam_masuk = t.karyawan.nama_karyawan if t.karyawan else None
        nama_satpam_keluar = None
        if t.nik_satpam_keluar:
            sk = db.query(Karyawan).filter(Karyawan.nik == t.nik_satpam_keluar).first()
            if sk:
                nama_satpam_keluar = sk.nama_karyawan

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
            "foto_masuk": _build_foto_url(t.foto),
            "foto_keluar": _build_foto_url(t.foto_keluar),
            "status": "KELUAR" if t.jam_keluar else "MASUK",
            "nik_masuk": t.nik_satpam,
            "nama_satpam_masuk": nama_satpam_masuk,
            "nik_keluar": t.nik_satpam_keluar,
            "nama_satpam_keluar": nama_satpam_keluar,
        })

    return {
        "status": True,
        "shift_aktif": shift_aktif,
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
    jam_masuk: Optional[str] = Form(None),  # timestamp WIB dari device Android
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Validate User & Shift
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")

    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={
            "status": False,
            "message": shift_check["message"]
        })


    if no_pol and no_pol.strip() == "":
        no_pol = None

    # 2. Handle Image
    foto_path = None
    if foto:
        foto_path = save_compressed_image(foto, "tamu_masuk")
        
    # 3. Save DB — gunakan raw SQL agar jam_masuk tersimpan dalam WIB (bukan UTC)
    # Prioritas: jam_masuk dari Android device (sudah WIB), fallback ke now_wib()
    if jam_masuk:
        jam_masuk_wib = jam_masuk  # dari Android device, sudah WIB
    else:
        jam_masuk_wib = now_wib().strftime('%Y-%m-%d %H:%M:%S')  # fallback
    logger.info(f"[StoreTamu] jam_masuk yang dipakai: {jam_masuk_wib} (sumber: {'android' if jam_masuk else 'server'})")

    from sqlalchemy import text as sql_text
    result = db.execute(sql_text("""
        INSERT INTO tamu (nik_satpam, nama, alamat, jenis_id, no_telp, perusahaan,
                         bertemu_dengan, dengan_perjanjian, keperluan,
                         jenis_kendaraan, no_pol, jam_masuk, foto)
        VALUES (:nik_satpam, :nama, :alamat, :jenis_id, :no_telp, :perusahaan,
                :bertemu_dengan, :dengan_perjanjian, :keperluan,
                :jenis_kendaraan, :no_pol, :jam_masuk, :foto)
    """), {
        "nik_satpam": user.nik,
        "nama": nama,
        "alamat": alamat,
        "jenis_id": jenis_id,
        "no_telp": no_telp,
        "perusahaan": perusahaan,
        "bertemu_dengan": bertemu_dengan,
        "dengan_perjanjian": dengan_perjanjian,
        "keperluan": keperluan,
        "jenis_kendaraan": jenis_kendaraan,
        "no_pol": no_pol,
        "jam_masuk": jam_masuk_wib,
        "foto": foto_path
    })
    db.commit()
    new_id = result.lastrowid

    # Ambil data yang baru disimpan
    new_tamu = db.query(Tamu).filter(Tamu.id_tamu == new_id).first()

    
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
    foto_keluar: UploadFile = File(...),           # match field name dari Android
    jam_keluar: Optional[str] = Form(None),         # timestamp WIB dari device Android
    kode_jam_kerja: Optional[str] = Form(None),     # opsional dari Android
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Validate User & Shift
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    if not karyawan:
        raise HTTPException(404, "Data karyawan tidak ditemukan")

    # Validasi shift: satpam harus dalam jam kerja aktif dan belum absen pulang
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={
            "status": False,
            "message": shift_check["message"]
        })


    # 2. Get Tamu
    tamu = db.query(Tamu).filter(Tamu.id_tamu == id_tamu).first()
    if not tamu:
        raise HTTPException(404, "Tamu tidak ditemukan")

    # 3. Handle Image
    foto_keluar_path = save_compressed_image(foto_keluar, "tamu_keluar")

    # 4. Tentukan jam_keluar — prioritas dari Android (sudah WIB), fallback server
    if jam_keluar:
        jam_keluar_wib = jam_keluar
    else:
        jam_keluar_wib = now_wib().strftime('%Y-%m-%d %H:%M:%S')

    logger.info(f"[TamuPulang] id={id_tamu} jam_keluar={jam_keluar_wib} (sumber: {'android' if jam_keluar else 'server'})")

    # 5. Update DB via raw SQL agar jam_keluar tersimpan WIB
    from sqlalchemy import text as sql_text
    db.execute(sql_text("""
        UPDATE tamu 
        SET jam_keluar = :jam_keluar,
            nik_satpam_keluar = :nik,
            foto_keluar = :foto
        WHERE id_tamu = :id_tamu
    """), {
        "jam_keluar": jam_keluar_wib,
        "nik": user.nik,
        "foto": foto_keluar_path,
        "id_tamu": id_tamu
    })
    db.commit()

    # 6. Refresh dan return
    db.refresh(tamu)

    base_url = "https://frontend.k3guard.com/api-py/storage/"
    return {
        "status": True,
        "message": "Tamu Berhasil Keluar",
        "data": {
            "id": tamu.id_tamu,
            "nama": tamu.nama,
            "jam_masuk": str(tamu.jam_masuk) if tamu.jam_masuk else None,
            "jam_keluar": jam_keluar_wib,
            "foto_masuk": f"{base_url}{tamu.foto}" if tamu.foto else None,
            "foto_keluar": f"{base_url}{foto_keluar_path}" if foto_keluar_path else None,
            "status": "KELUAR"
        }
    }



