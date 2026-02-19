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
    
    # By DATE
    # Note: SetJamKerjaByDate/Day were renamed/refactored in prev steps.
    jk_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today).first()
    if jk_date:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_date.kode_jam_kerja).first()
        
    # By DAY
    jk_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == namahari).first()
    if jk_day:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_day.kode_jam_kerja).first()
        
    # By DEPT
    # Logic mirror of PHP
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

def save_upload_surat(file_obj: UploadFile, kode_cabang: str, subfolder_name: str) -> str:
    # uploads/$kodeCabang/$subfolder_name/filename.jpg
    # In python we usually map storage path.
    # PHP: Storage::disk('public')->put...
    # Path: storage/app/public/uploads/KODE_CABANG/suratmasuk/...
    
    base_dir = f"/var/www/appPatrol/storage/app/public/uploads/{kode_cabang}/{subfolder_name}"
    os.makedirs(base_dir, exist_ok=True)
    
    # Filename like PHP: time()_context_random.jpg
    # context is 'suratmasuk' etc
    safe_name = f"{int(datetime.timestamp(datetime.now()))}_{subfolder_name}_{uuid.uuid4().hex[:6]}.jpg"
    target_path = os.path.join(base_dir, safe_name)
    
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file_obj.file, buffer)
    except Exception as e:
        print(f"Error saving image: {e}")
        return None
        
    return f"uploads/{kode_cabang}/{subfolder_name}/{safe_name}"

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
    
    kode_cabang = karyawan.kode_cabang
    now = datetime.now()
    last_month = now - timedelta(days=30) # approx subMonth
    
    # Query
    # Join surat_masuk with karyawan (satpam)
    # Filter by kode_cabang (via satpam.kode_cabang)
    # Filter date range OR null accepted
    
    # Note: Karyawan -> Satpam join
    
    q = db.query(SuratMasuk, Karyawan.nama_karyawan.label("nama_satpam"))\
        .outerjoin(Karyawan, SuratMasuk.nik_satpam == Karyawan.nik)\
        .filter(Karyawan.kode_cabang == kode_cabang)\
        .filter(or_(
            and_(SuratMasuk.tanggal_surat >= last_month, SuratMasuk.tanggal_surat <= now),
            SuratMasuk.tanggal_diterima == None
        ))\
        .order_by(text("surat_masuk.tanggal_diterima IS NULL ASC"), SuratMasuk.id.desc())
        
    results = q.all()
    
    data = []
    for sm, nama_satpam in results:
        # Construct url
        foto_url = None
        if sm.foto:
            foto_url = f"https://frontend.k3guard.com/api-py/storage/{sm.foto}" 
            
        sm_dict = {c.name: getattr(sm, c.name) for c in sm.__table__.columns}
        sm_dict['nama_karyawan'] = nama_satpam # key matches PHP response
        sm_dict['foto_url'] = foto_url
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
    
    # 🛡️ PRODUKSI SAFE: prioritas presensi, fallback ke jam kerja
    presensi = check_sedang_bertugas(karyawan.nik, db)
    if not presensi:
        cek = check_jam_kerja(karyawan, db)
        if not cek['status']:
             raise HTTPException(status_code=403, detail=cek['message'])
             
    # Logic
    nik = karyawan.nik
    kode_cabang = karyawan.kode_cabang
    
    # Generate Nomor
    # PHP: "SM".now()->format('Ymd').rand(100,999)
    nomor = f"SM{datetime.now().strftime('%Y%m%d')}{random.randint(100, 999)}"
    
    foto_path = None
    if foto:
        foto_path = save_upload_surat(foto, kode_cabang, 'suratmasuk')
        
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
    
    return {"status": True, "data": new_sm}

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
    
    # Check Shift
    presensi = check_sedang_bertugas(karyawan.nik, db)
    if not presensi:
        cek = check_jam_kerja(karyawan, db)
        if not cek['status']:
             raise HTTPException(status_code=403, detail=cek['message'])
             
    sm = db.query(SuratMasuk).filter(SuratMasuk.id == id).first()
    if not sm: raise HTTPException(404, "Surat Masuk not found")
    
    foto_path = None
    if foto_penerima:
        foto_path = save_upload_surat(foto_penerima, karyawan.kode_cabang, 'suratditerima')
        
    sm.status_surat = 'SELESAI'
    sm.status_penerimaan = 'DITERIMA'
    sm.nama_penerima = nama_penerima
    sm.no_penerima = no_penerima
    sm.tanggal_diterima = datetime.now()
    sm.nik_satpam_pengantar = karyawan.nik
    if foto_path:
        sm.foto_penerima = foto_path
        
    db.commit()
    return {"status": True}

# ===============================================
# SURAT KELUAR
# ===============================================

@router.get("/suratkeluar")
async def surat_keluar(
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # Logic similar to surat masuk
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    kode_cabang = karyawan.kode_cabang
    now = datetime.now()
    last_month = now - timedelta(days=30)
    
    from sqlalchemy.orm import aliased

    # Aliases
    Satpam = aliased(Karyawan)
    Pengantar = aliased(Karyawan)
    
    q = db.query(
        SuratKeluar, 
        Satpam.nama_karyawan.label("nama_satpam"),
        Pengantar.nama_karyawan.label("nama_pengantar")
    )\
        .outerjoin(Satpam, SuratKeluar.nik_satpam == Satpam.nik)\
        .outerjoin(Pengantar, SuratKeluar.nik_satpam_pengantar == Pengantar.nik)\
        .filter(Satpam.kode_cabang == kode_cabang)\
        .filter(or_(
            and_(SuratKeluar.tanggal_surat >= last_month, SuratKeluar.tanggal_surat <= now),
            SuratKeluar.tanggal_diterima == None
        ))\
        .order_by(text("surat_keluar.tanggal_diterima IS NULL ASC"), SuratKeluar.id.desc())
        
    results = q.all()
    
    data = []
    for sk, n_satpam, n_pengantar in results:
        foto_url = f"https://frontend.k3guard.com/api-py/storage/{sk.foto}" if sk.foto else None
        
        sk_dict = {c.name: getattr(sk, c.name) for c in sk.__table__.columns}
        sk_dict['nama_satpam'] = n_satpam
        sk_dict['nama_pengantar'] = n_pengantar
        sk_dict['foto_url'] = foto_url
        data.append(sk_dict)
        
    return {
        "status": True,
        "data": data
    }

@router.post("/suratkeluar/store")
async def tambah_surat_keluar(
    tujuan_surat: str = Form(...),
    perihal: Optional[str] = Form(None), # Not required in PHP validation but used in insert?
    foto: Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # PHP: validate(['tujuan_surat'=>'required']) - perihal not required? 
    # But in insert: 'perihal'=>$request->perihal. If null, might fail if column not nullable.
    # Model SuratKeluar: perihal is NOT NULL. So it should be required.
    
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    
    # PHP doesn't check shift for surat keluar store? 
    # Logic in `tambahSuratKeluar` (lines 241-270) DOES NOT call cekSedangBertugas.
    # So I wont either.
    
    nomor = f"SK{datetime.now().strftime('%Y%m%d')}{random.randint(100, 999)}"
    
    foto_path = None
    if foto:
        foto_path = save_upload_surat(foto, karyawan.kode_cabang, 'suratkeluar')
        
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
    
    return {"status": True, "data": new_sk}

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
    
    sk = db.query(SuratKeluar).filter(SuratKeluar.id == id).first()
    if not sk: raise HTTPException(404, "Surat Keluar not found")
    
    foto_path = None
    if foto_penerima:
        # PHP uses 'suratkeluar-penerima' as context string which likely becomes subfolder?
        # storeCompressedDocument(file, "uploads/$kodeCabang/suratkeluar", 'suratkeluar-penerima')
        # Wait, storeCompressedDocument 2nd arg is folder. 3rd arg is context (prefix).
        # My clean mapping: folder = suratkeluar
        foto_path = save_upload_surat(foto_penerima, karyawan.kode_cabang, 'suratkeluar')
        
    sk.status_surat = 'SELESAI'
    sk.status_penerimaan = 'DITERIMA'
    sk.nama_penerima = nama_penerima
    sk.no_penerima = no_penerima
    sk.tanggal_diterima = datetime.now()
    sk.nik_satpam_pengantar = karyawan.nik
    if foto_path:
        sk.foto_penerima = foto_path
        
    db.commit()
    return {"status": True}
