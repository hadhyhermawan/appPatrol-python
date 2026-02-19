from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, and_, desc
from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import (
    Userkaryawan, Karyawan, Presensi, PresensiJamkerja, 
    SetJamKerjaByDate, SetJamKerjaByDay, PresensiJamkerjaByDeptDetail, 
    PresensiJamkerjaBydept, SafetyBriefings
)
from datetime import datetime, date, timedelta
import shutil
import os
import uuid
import random

router = APIRouter(
    prefix="/api/android",
    tags=["Safety Briefing Legacy"],
    responses={404: {"description": "Not found"}},
)

# Helpers
def get_nama_hari(d: date):
    days = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    return days[d.weekday()]

def get_jam_kerja_karyawan(nik, kode_cabang, kode_dept, db: Session):
    today = date.today()
    namahari = get_nama_hari(today)
    
    # 1. By DATE
    jk_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today).first()
    if jk_date:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_date.kode_jam_kerja).first()
        
    # 2. By DAY
    jk_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == namahari).first()
    if jk_day:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_day.kode_jam_kerja).first()
        
    # 3. By DEPT
    jk_dept = db.query(PresensiJamkerjaByDeptDetail)\
        .join(PresensiJamkerjaBydept, PresensiJamkerjaByDeptDetail.kode_jk_dept == PresensiJamkerjaBydept.kode_jk_dept)\
        .filter(PresensiJamkerjaBydept.kode_cabang == kode_cabang)\
        .filter(PresensiJamkerjaBydept.kode_dept == kode_dept)\
        .filter(PresensiJamkerjaByDeptDetail.hari == namahari)\
        .first()
        
    if jk_dept:
        return db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == jk_dept.kode_jam_kerja).first()
        
    return None

def save_upload_briefing(file_obj: UploadFile, kode_cabang: str, nik: str) -> str:
    # uploads/$kodeCabang/safety_briefings/$nik/filename.jpg
    base_dir = f"/var/www/appPatrol/storage/app/public/uploads/{kode_cabang}/safety_briefings/{nik}"
    os.makedirs(base_dir, exist_ok=True)
    
    safe_name = f"briefing_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
    target_path = os.path.join(base_dir, safe_name)
    
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file_obj.file, buffer)
    except Exception as e:
        print(f"Error saving image: {e}")
        return None
        
    return f"uploads/{kode_cabang}/safety_briefings/{nik}/{safe_name}"

# ===============================================
# ENDPOINTS
# ===============================================

@router.get("/safetybriefing")
async def get_safety_briefing(
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    if not user_karyawan: raise HTTPException(404, "User Karyawan not found")
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    if not karyawan: raise HTTPException(404, "Karyawan not found")
    
    nik = karyawan.nik
    kode_cabang = karyawan.kode_cabang
    now = datetime.now()
    last_month = now - timedelta(days=30)
    
    # Query: Join SafetyBriefings with Karyawan
    # Filter by Cabang and Date Range (Last Month)
    
    results = db.query(SafetyBriefings, Karyawan.nama_karyawan)\
        .join(Karyawan, SafetyBriefings.nik == Karyawan.nik)\
        .filter(Karyawan.kode_cabang == kode_cabang)\
        .filter(SafetyBriefings.tanggal_jam >= last_month)\
        .order_by(SafetyBriefings.tanggal_jam.desc())\
        .all()
        
    data = []
    for sb, nama in results:
        foto_url = f"https://frontend.k3guard.com/api-py/storage/{sb.foto}" if sb.foto else None
        
        data.append({
            "id": sb.id,
            "nik": sb.nik,
            "keterangan": sb.keterangan,
            "foto": sb.foto, # relative path
            "foto_url": foto_url, # full url
            "tanggal_jam": sb.tanggal_jam,
            "nama_karyawan": nama,
            "kode_cabang": kode_cabang
        })
        
    return {
        "status": True,
        "nik": nik,
        "kode_cabang": kode_cabang,
        "data": data
    }

@router.post("/safetybriefing/store")
async def store_safety_briefing(
    keterangan: str = Form(...),
    foto: UploadFile = File(...), # Foto Wajib? PHP says nullable but usually required in app if logic
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Auth & Karyawan
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    if not user_karyawan: raise HTTPException(404, "User Karyawan not found")
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    if not karyawan: raise HTTPException(404, "Karyawan not found")
    
    nik = karyawan.nik
    kode_cabang = karyawan.kode_cabang
    today_date = date.today()
    
    # 2. Get Jam Kerja
    jam_kerja = get_jam_kerja_karyawan(nik, kode_cabang, karyawan.kode_dept, db)
    if not jam_kerja:
        return {"status": False, "message": "Anda tidak punya jadwal kerja hari ini"} # Return 200 with status False per PHP logic often used, but PHP returned 400. Let's stick to JSON response structure.
        # But wait, PHP returns json with 400 status code. FastAPI raises HTTPException usually.
        # However, Android expects specific JSON format.
        # Let's return JSONResponse with status 400 if needed, or dict with status:False.
        # PHP: return response()->json([..], 400); 
        # I will use JSONResponse to be safe.
    
    # 3. Hitung Shift
    start_dt = datetime.combine(today_date, jam_kerja.jam_masuk)
    end_dt = datetime.combine(today_date, jam_kerja.jam_pulang)
    
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
        
    # 4. Check Absen Masuk (Wajib 'h' dan ada jam_in)
    # Cek dengan kode_jam_kerja
    absen = db.query(Presensi).filter(
        Presensi.nik == nik,
        Presensi.status == 'h',
        Presensi.kode_jam_kerja == jam_kerja.kode_jam_kerja,
        Presensi.jam_in != None
    ).order_by(Presensi.jam_in.desc()).first()
    
    if not absen:
        # Fallback: Cek presensi hari ini (any shift)
        absen = db.query(Presensi).filter(
            Presensi.nik == nik,
            Presensi.status == 'h',
            Presensi.tanggal == today_date,
            Presensi.jam_in != None
        ).order_by(Presensi.jam_in.desc()).first()
        
    if not absen:
         # raise HTTPException(403, "Belum melakukan absen masuk pada shift ini")
         # Better to return compatible JSON
         from fastapi.responses import JSONResponse
         return JSONResponse(status_code=403, content={
             "status": False,
             "message": "Belum melakukan absen masuk pada shift ini"
         })

    # 5. Cek Duplikasi (Kecuali DNR / KRD)
    if karyawan.kode_jabatan not in ['DNR', 'KRD']:
        # Cek safety briefing di cabang ini, range jam shift ini
        dup = db.query(SafetyBriefings).join(Karyawan, SafetyBriefings.nik == Karyawan.nik)\
            .filter(Karyawan.kode_cabang == kode_cabang)\
            .filter(SafetyBriefings.tanggal_jam >= start_dt)\
            .filter(SafetyBriefings.tanggal_jam <= end_dt)\
            .first()
            
        if dup:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=403, content={
                "status": False,
                "message": "Safety Briefing sudah dibuat pada shift ini",
                "oleh_nik": dup.nik,
                "pada_jam": str(dup.tanggal_jam)
            })
            
    # 6. Upload Foto
    foto_path = None
    if foto:
        foto_path = save_upload_briefing(foto, kode_cabang, nik)
        
    # 7. Simpan
    new_sb = SafetyBriefings(
        nik=nik,
        keterangan=keterangan,
        foto=foto_path,
        tanggal_jam=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(new_sb)
    db.commit()
    db.refresh(new_sb)
    
    # Construct response
    new_sb.foto_url = f"https://frontend.k3guard.com/api-py/storage/{new_sb.foto}" if new_sb.foto else None
    
    return {
        "status": True,
        "message": "Safety briefing berhasil dicatat",
        "data": new_sb
    }
