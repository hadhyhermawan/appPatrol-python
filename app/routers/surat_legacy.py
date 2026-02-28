from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_, desc
from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import (
    SuratMasuk, SuratKeluar, Karyawan, Userkaryawan, Presensi, 
    PresensiJamkerja, SetJamKerjaByDate, SetJamKerjaByDay, 
    PresensiJamkerjaByDeptDetail, PresensiJamkerjaBydept
)
from datetime import datetime, date, time, timedelta
import shutil
import os
import uuid
import random
from typing import Optional, List
from PIL import Image
import io

router = APIRouter(
    prefix="/api/android",
    tags=["Surat Legacy"],
    responses={404: {"description": "Not found"}},
)

# Helpers
def get_nama_hari(d: date):
    days = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    return days[d.weekday()]

def get_jam_kerja_karyawan(nik, kode_cabang, kode_dept, db: Session):
    today = date.today()
    namahari = get_nama_hari(today)

    # 0.5 By Team Bulk Schedule
    try:
        from app.models.models import PresensiJamkerjaBydateExtra, EmployeeSchedule
        jk_extra = db.query(PresensiJamkerja)\
            .join(PresensiJamkerjaBydateExtra, PresensiJamkerjaBydateExtra.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .filter(PresensiJamkerjaBydateExtra.nik == nik)\
            .filter(PresensiJamkerjaBydateExtra.tanggal == today)\
            .first()
        if jk_extra:
            return jk_extra
            
        bs = db.query(EmployeeSchedule).filter(
            EmployeeSchedule.nik == nik,
            EmployeeSchedule.tanggal == today
        ).first()
        if bs:
            jk_bulk = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == bs.kode_jam_kerja).first()
            if jk_bulk:
                return jk_bulk
    except Exception:
        pass

    # 1. By DATE (Tukar Shift / Rotasi)
    jk_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today).first()
    if jk_date:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_date.kode_jam_kerja).first()

    # 2. By DAY (Jadwal Rutin Personal)
    jk_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == namahari).first()
    if jk_day:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_day.kode_jam_kerja).first()

    # 3. By DEPT (Jadwal Default Departemen)
    jk_dept = db.query(PresensiJamkerjaByDeptDetail)\
        .join(PresensiJamkerjaBydept, PresensiJamkerjaByDeptDetail.kode_jk_dept == PresensiJamkerjaBydept.kode_jk_dept)\
        .filter(PresensiJamkerjaBydept.kode_cabang == kode_cabang)\
        .filter(PresensiJamkerjaBydept.kode_dept == kode_dept)\
        .filter(PresensiJamkerjaByDeptDetail.hari == namahari)\
        .first()

    if jk_dept:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_dept.kode_jam_kerja).first()

    return None

def check_sedang_bertugas(nik: str, db: Session):
    # Validasi Presensi: jam_in not null, jam_out null
    # PHP: order by tanggal desc, jam_in desc
    return db.query(Presensi).filter(
        Presensi.nik == nik,
        Presensi.jam_in != None, 
        Presensi.jam_out == None
    ).order_by(Presensi.tanggal.desc(), Presensi.jam_in.desc()).first()

def check_jam_kerja(karyawan, db: Session):
    jam_kerja = get_jam_kerja_karyawan(karyawan.nik, karyawan.kode_cabang, karyawan.kode_dept, db)
    if not jam_kerja:
        return {"status": False, "message": "Anda tidak memiliki jadwal shift hari ini."}
        
    now = datetime.now()
    # Parse times
    # Assuming jam_masuk and jam_pulang are time objects or strings
    # We need full datetime to compare. using today's date.
    today_str = date.today().isoformat()
    
    start_dt = datetime.strptime(f"{today_str} {jam_kerja.jam_masuk}", "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(f"{today_str} {jam_kerja.jam_pulang}", "%Y-%m-%d %H:%M:%S")
    
    # Handle Lintashari? PHP uses Carbon::parse which handles times. 
    # If end < start, it's next day.
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
        # If now is before start (e.g. 01:00, start 20:00), maybe it belongs to yesterday shift?
        # But this function checks "today's" schedule.
        # PHP logic: if ($now->lt($start) || $now->gt($end))
        
    if now < start_dt or now > end_dt:
        return {
            "status": False, 
            "message": f"Anda sedang di luar jam kerja ({jam_kerja.jam_masuk} - {jam_kerja.jam_pulang})"
        }
        
    return {"status": True}

def save_upload_surat(file_obj: UploadFile, kode_cabang: str, subfolder_name: str) -> tuple:
    base_dir = f"/var/www/appPatrol-python/storage/uploads/{kode_cabang}/{subfolder_name}"
    os.makedirs(base_dir, exist_ok=True)
    
    unique_hex = uuid.uuid4().hex[:6]
    safe_name = f"{int(datetime.timestamp(datetime.now()))}_{subfolder_name}_{unique_hex}.jpg"
    safe_name_thumb = f"{int(datetime.timestamp(datetime.now()))}_{subfolder_name}_{unique_hex}_thumb.jpg"
    target_path = os.path.join(base_dir, safe_name)
    target_path_thumb = os.path.join(base_dir, safe_name_thumb)
    
    try:
        # Read image
        image_content = file_obj.file.read()
        image = Image.open(io.BytesIO(image_content))
        
        # Convert to RGB if needed
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
            
        # Resize: Max width 1400, keep aspect ratio
        max_width = 1400
        if image.width > max_width:
            ratio = max_width / image.width
            new_height = int(image.height * ratio)
            image_large = image.resize((max_width, new_height), Image.Resampling.LANCZOS)
        else:
            image_large = image
            
        # Save compressed
        image_large.save(target_path, "JPEG", quality=70)

        # Thumbnail
        thumb_width = 300
        if image.width > thumb_width:
            ratio = thumb_width / image.width
            new_height = int(image.height * ratio)
            image_thumb = image.resize((thumb_width, new_height), Image.Resampling.LANCZOS)
        else:
            image_thumb = image
            
        image_thumb.save(target_path_thumb, "JPEG", quality=60)

        file_obj.file.seek(0)
        
        return f"uploads/{kode_cabang}/{subfolder_name}/{safe_name}", f"uploads/{kode_cabang}/{subfolder_name}/{safe_name_thumb}"
    except Exception as e:
        print(f"Error saving image with PIL: {e}")
        with open(target_path, "wb") as buffer:
             buffer.write(image_content)
        return f"uploads/{kode_cabang}/{subfolder_name}/{safe_name}", None

# ===============================================
# SURAT MASUK
# ===============================================

@router.get("/suratmasuk")
async def surat_masuk(
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    if not user_karyawan: raise HTTPException(404, "Relasi UserKaryawan not found")
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    if not karyawan: raise HTTPException(404, "Karyawan not found")

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        return {"status": True, "kode_cabang": karyawan.kode_cabang, "data": []}

    kode_cabang = karyawan.kode_cabang
    now = datetime.now()
    last_month = now - timedelta(days=30)

    from sqlalchemy.orm import aliased
    Satpam = aliased(Karyawan)
    Pengantar = aliased(Karyawan)

    q = db.query(
        SuratMasuk, 
        Satpam.nama_karyawan.label("nama_petugas_penerima"),
        Pengantar.nama_karyawan.label("nama_petugas_pengantar")
    )\
        .outerjoin(Satpam, SuratMasuk.nik_petugas == Satpam.nik)\
        .outerjoin(Pengantar, SuratMasuk.nik_satpam_pengantar == Pengantar.nik)\
        .filter(Satpam.kode_cabang == kode_cabang)\
        .filter(or_(
            and_(SuratMasuk.tanggal_surat >= last_month, SuratMasuk.tanggal_surat <= now),
            SuratMasuk.tanggal_diterima == None
        ))\
        .order_by(text("surat_masuk.tanggal_diterima IS NULL ASC"), SuratMasuk.id.desc())

    results = q.all()
    data = []
    base_url = "https://frontend.k3guard.com/api-py/storage/"
    for sm, n_penerima, n_pengantar in results:
        foto_url = f"{base_url}{sm.foto.replace('.jpg', '_thumb.jpg')}" if sm.foto else None
        foto_url_original = f"{base_url}{sm.foto}" if sm.foto else None
        
        sm_dict = {c.name: getattr(sm, c.name) for c in sm.__table__.columns}
        sm_dict['nama_petugas_penerima'] = n_penerima
        sm_dict['nama_petugas_pengantar'] = n_pengantar
        sm_dict['foto_url'] = foto_url
        sm_dict['foto_url_original'] = foto_url_original
        data.append(sm_dict)

    return {
        "status": True,
        "kode_cabang": kode_cabang,
        "data": data
    }

@router.post("/suratmasuk/store")
async def tambah_surat_masuk(
    asal_surat: str = Form(...),
    tujuan_surat: str = Form(...),
    perihal: str = Form(...),
    foto: Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        raise HTTPException(status_code=403, detail=shift_check["message"])
             
    # Logic
    nik = karyawan.nik
    kode_cabang = karyawan.kode_cabang
    
    # Generate Nomor
    # PHP: "SM".now()->format('Ymd').rand(100,999)
    nomor = f"SM{datetime.now().strftime('%Y%m%d')}{random.randint(100, 999)}"
    
    foto_path = None
    foto_thumb_path = None
    if foto:
        foto_path, foto_thumb_path = save_upload_surat(foto, kode_cabang, 'suratmasuk')
        
    new_sm = SuratMasuk(
        nomor_surat=nomor,
        tanggal_surat=datetime.now(),
        asal_surat=asal_surat,
        tujuan_surat=tujuan_surat,
        perihal=perihal,
        foto=foto_path,
        status_surat='MASUK',
        nik_satpam=nik
    )
    
    db.add(new_sm)
    db.commit()
    db.refresh(new_sm)

    base_url = "https://frontend.k3guard.com/api-py/storage/"
    foto_url = f"{base_url}{foto_thumb_path}" if foto_thumb_path else (f"{base_url}{new_sm.foto}" if new_sm.foto else None)
    foto_url_original = f"{base_url}{new_sm.foto}" if new_sm.foto else None

    return {
        "status": True,
        "message": "Surat masuk berhasil disimpan",
        "data": {
            "id": new_sm.id,
            "nomor_surat": new_sm.nomor_surat,
            "tanggal_surat": str(new_sm.tanggal_surat),
            "asal_surat": new_sm.asal_surat,
            "tujuan_surat": new_sm.tujuan_surat,
            "perihal": new_sm.perihal,
            "foto": new_sm.foto,
            "foto_url": foto_url,
            "foto_url_original": foto_url_original,
            "nik_satpam": new_sm.nik_satpam,
            "nik_satpam_pengantar": new_sm.nik_satpam_pengantar,
            "status_surat": new_sm.status_surat,
            "tanggal_update": str(new_sm.tanggal_update) if new_sm.tanggal_update else None,
            "status_penerimaan": getattr(new_sm, 'status_penerimaan', None),
            "tanggal_diterima": None,
            "nama_petugas_penerima": karyawan.nama_karyawan,
            "nama_petugas_pengantar": None,
            "nama_penerima": None,
            "no_penerima": None
        }
    }

@router.post("/suratmasuk/status/{id}")
async def update_surat_masuk(
    id: int,
    nama_penerima: str = Form(...),
    no_penerima: Optional[str] = Form(None),
    foto_penerima: Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        raise HTTPException(status_code=403, detail=shift_check["message"])
             
    sm = db.query(SuratMasuk).filter(SuratMasuk.id == id).first()
    if not sm: raise HTTPException(404, "Surat Masuk not found")
    
    foto_path = None
    foto_thumb_path = None
    if foto_penerima:
        foto_path, foto_thumb_path = save_upload_surat(foto_penerima, karyawan.kode_cabang, 'suratditerima')
        
    sm.status_surat = 'SELESAI'
    sm.status_penerimaan = 'DITERIMA'
    sm.nama_penerima = nama_penerima
    sm.no_penerima = no_penerima
    sm.tanggal_diterima = datetime.now()
    sm.nik_satpam_pengantar = karyawan.nik
    if foto_path:
        sm.foto_penerima = foto_path
        
    db.commit()
    db.refresh(sm)

    base_url = "https://frontend.k3guard.com/api-py/storage/"
    foto_url = f"{base_url}{sm.foto}" if sm.foto else None
    foto_penerima_url = f"{base_url}{sm.foto_penerima}" if getattr(sm, 'foto_penerima', None) else None

    return {
        "status": True,
        "message": "Status surat berhasil diperbarui",
        "data": {
            "id": sm.id,
            "nomor_surat": sm.nomor_surat,
            "tanggal_surat": str(sm.tanggal_surat),
            "asal_surat": sm.asal_surat,
            "tujuan_surat": sm.tujuan_surat,
            "perihal": sm.perihal,
            "foto": sm.foto,
            "foto_url": f"{base_url}{sm.foto.replace('.jpg', '_thumb.jpg')}" if sm.foto else None,
            "foto_url_original": f"{base_url}{sm.foto}" if sm.foto else None,
            "foto_penerima": getattr(sm, 'foto_penerima', None),
            "foto_penerima_url": f"{base_url}{foto_thumb_path}" if foto_thumb_path else foto_penerima_url,
            "foto_penerima_url_original": foto_penerima_url,
            "nik_satpam": sm.nik_satpam,
            "nik_satpam_pengantar": sm.nik_satpam_pengantar,
            "status_surat": sm.status_surat,
            "tanggal_update": str(sm.tanggal_update) if sm.tanggal_update else None,
            "status_penerimaan": getattr(sm, 'status_penerimaan', None),
            "tanggal_diterima": str(sm.tanggal_diterima) if sm.tanggal_diterima else None,
            "nama_satpam": karyawan.nama_karyawan,
            "nama_pengantar": karyawan.nama_karyawan,
            "nama_penerima": sm.nama_penerima,
            "no_penerima": sm.no_penerima
        }
    }

# ===============================================
# SURAT KELUAR
# ===============================================

@router.get("/suratkeluar")
async def surat_keluar(
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    if not karyawan: raise HTTPException(404, "Karyawan not found")

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        return {"status": True, "data": []}

    kode_cabang = karyawan.kode_cabang
    now = datetime.now()
    last_month = now - timedelta(days=30)

    from sqlalchemy.orm import aliased
    Satpam = aliased(Karyawan)
    Pengantar = aliased(Karyawan)

    q = db.query(
        SuratKeluar,
        Satpam.nama_karyawan.label("nama_satpam"),
        Pengantar.nama_karyawan.label("nama_pengantar")
    )\
        .outerjoin(Satpam, SuratKeluar.nik_petugas == Satpam.nik)\
        .outerjoin(Pengantar, SuratKeluar.nik_petugas_pengantar == Pengantar.nik)\
        .filter(Satpam.kode_cabang == kode_cabang)\
        .filter(or_(
            and_(SuratKeluar.tanggal_surat >= last_month, SuratKeluar.tanggal_surat <= now),
            SuratKeluar.tanggal_diterima == None
        ))\
        .order_by(text("surat_keluar.tanggal_diterima IS NULL ASC"), SuratKeluar.id.desc())

    results = q.all()
    data = []
    base_url = "https://frontend.k3guard.com/api-py/storage/"
    for sk, n_satpam, n_pengantar in results:
        foto_url = f"{base_url}{sk.foto.replace('.jpg', '_thumb.jpg')}" if sk.foto else None
        foto_url_original = f"{base_url}{sk.foto}" if sk.foto else None
        sk_dict = {c.name: getattr(sk, c.name) for c in sk.__table__.columns}
        sk_dict['nama_satpam'] = n_satpam
        sk_dict['nama_pengantar'] = n_pengantar
        sk_dict['foto_url'] = foto_url
        sk_dict['foto_url_original'] = foto_url_original
        data.append(sk_dict)

    return {
        "status": True,
        "data": data
    }

@router.post("/suratkeluar/store")
async def tambah_surat_keluar(
    tujuan_surat: str = Form(...),
    perihal: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        raise HTTPException(status_code=403, detail=shift_check["message"])

    nomor = f"SK{datetime.now().strftime('%Y%m%d')}{random.randint(100, 999)}"
    
    foto_path = None
    foto_thumb_path = None
    if foto:
        foto_path, foto_thumb_path = save_upload_surat(foto, karyawan.kode_cabang, 'suratkeluar')
        
    new_sk = SuratKeluar(
        nomor_surat=nomor,
        tanggal_surat=datetime.now(),
        tujuan_surat=tujuan_surat,
        perihal=perihal or "-", # Default if missing
        foto=foto_path,
        status_surat='KELUAR',
        nik_satpam=karyawan.nik
    )
    
    db.add(new_sk)
    db.commit()
    db.refresh(new_sk)

    base_url = "https://frontend.k3guard.com/api-py/storage/"
    foto_url = f"{base_url}{new_sk.foto}" if new_sk.foto else None

    return {
        "status": True,
        "message": "Surat keluar berhasil disimpan",
        "data": {
            "id": new_sk.id,
            "nomor_surat": new_sk.nomor_surat,
            "tanggal_surat": str(new_sk.tanggal_surat),
            "tujuan_surat": new_sk.tujuan_surat,
            "perihal": new_sk.perihal,
            "foto": new_sk.foto,
            "foto_url": f"{base_url}{foto_thumb_path}" if foto_thumb_path else (f"{base_url}{new_sk.foto}" if new_sk.foto else None),
            "foto_url_original": f"{base_url}{new_sk.foto}" if new_sk.foto else None,
            "foto_penerima": None,
            "nik_satpam": new_sk.nik_satpam,
            "nik_satpam_pengantar": None,
            "nama_satpam": karyawan.nama_karyawan,
            "nama_pengantar": None,
            "nama_penerima": None,
            "no_penerima": None,
            "status_surat": new_sk.status_surat,
            "status_penerimaan": None,
            "tanggal_update": None,
            "tanggal_diterima": None
        }
    }

@router.post("/suratkeluar/status/{id}")
async def update_surat_keluar(
    id: int,
    nama_penerima: str = Form(...),
    no_penerima: Optional[str] = Form(None),
    foto_penerima: Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()

    from app.routers.tamu_legacy import check_jam_kerja_status
    shift_check = check_jam_kerja_status(db, karyawan)
    if not shift_check["status"]:
        raise HTTPException(status_code=403, detail=shift_check["message"])

    sk = db.query(SuratKeluar).filter(SuratKeluar.id == id).first()
    if not sk: raise HTTPException(404, "Surat Keluar not found")
    
    foto_path = None
    foto_thumb_path = None
    if foto_penerima:
        foto_path, foto_thumb_path = save_upload_surat(foto_penerima, karyawan.kode_cabang, 'suratkeluar')
        
    sk.status_surat = 'SELESAI'
    sk.status_penerimaan = 'DITERIMA'
    sk.nama_penerima = nama_penerima
    sk.no_penerima = no_penerima
    sk.tanggal_diterima = datetime.now()
    sk.nik_satpam_pengantar = karyawan.nik
    if foto_path:
        sk.foto_penerima = foto_path
        
    db.commit()
    db.refresh(sk)

    base_url = "https://frontend.k3guard.com/api-py/storage/"
    foto_url = f"{base_url}{sk.foto}" if sk.foto else None
    foto_penerima_url = f"{base_url}{sk.foto_penerima}" if getattr(sk, 'foto_penerima', None) else None

    return {
        "status": True,
        "message": "Status surat keluar berhasil diperbarui",
        "data": {
            "id": sk.id,
            "nomor_surat": sk.nomor_surat,
            "tanggal_surat": str(sk.tanggal_surat),
            "tujuan_surat": sk.tujuan_surat,
            "perihal": sk.perihal,
            "foto": sk.foto,
            "foto_url": f"{base_url}{sk.foto.replace('.jpg', '_thumb.jpg')}" if sk.foto else None,
            "foto_url_original": f"{base_url}{sk.foto}" if sk.foto else None,
            "foto_penerima": getattr(sk, 'foto_penerima', None),
            "foto_penerima_url": f"{base_url}{foto_thumb_path}" if foto_thumb_path else foto_penerima_url,
            "foto_penerima_url_original": foto_penerima_url,
            "nik_satpam": sk.nik_satpam,
            "nik_satpam_pengantar": sk.nik_satpam_pengantar,
            "nama_satpam": karyawan.nama_karyawan,
            "nama_pengantar": karyawan.nama_karyawan,
            "nama_penerima": sk.nama_penerima,
            "no_penerima": sk.no_penerima,
            "status_surat": sk.status_surat,
            "status_penerimaan": getattr(sk, 'status_penerimaan', None),
            "tanggal_update": str(sk.tanggal_update) if sk.tanggal_update else None,
            "tanggal_diterima": str(sk.tanggal_diterima) if sk.tanggal_diterima else None
        }
    }
