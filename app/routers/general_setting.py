from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import PengaturanUmum
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import time, datetime
import shutil
import os
import uuid

router = APIRouter(
    prefix="/api/settings/general",
    tags=["General Settings"],
    responses={404: {"description": "Not found"}},
)

UPLOAD_DIR = "/var/www/appPatrol/storage/app/public/logo"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class GeneralSettingDTO(BaseModel):
    id: int
    nama_perusahaan: str
    alamat: str
    telepon: str
    logo: str
    total_jam_bulan: int
    denda: int
    face_recognition: int
    periode_laporan_dari: int
    periode_laporan_sampai: int
    periode_laporan_next_bulan: int
    wa_api_key: str
    batasi_absen: int
    batas_jam_absen: int
    batas_jam_absen_pulang: int
    multi_lokasi: int
    notifikasi_wa: int
    batasi_hari_izin: int
    jml_hari_izin_max: int
    batas_presensi_lintashari: time
    toleransi_shift_malam_mulai: time
    toleransi_shift_malam_batas: time
    enable_face_block_system: int
    face_block_limit: int
    face_check_liveness_limit: int
    cloud_id: Optional[str]
    api_key: Optional[str]
    domain_email: Optional[str]
    domain_wa_gateway: Optional[str]
    min_supported_version_code: Optional[int]
    latest_version_code: Optional[int]
    update_url: Optional[str]
    update_message: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

@router.get("", response_model=GeneralSettingDTO)
async def get_general_setting(db: Session = Depends(get_db)):
    setting = db.query(PengaturanUmum).filter(PengaturanUmum.id == 1).first()
    if not setting:
        raise HTTPException(status_code=404, detail="Settings not found")
    return setting

@router.put("", response_model=GeneralSettingDTO)
async def update_general_setting(
    nama_perusahaan: str = Form(...),
    alamat: str = Form(...),
    telepon: str = Form(...),
    total_jam_bulan: int = Form(...),
    denda: int = Form(0), # Checkbox handling: 0 or 1
    face_recognition: int = Form(0),
    periode_laporan_dari: int = Form(...),
    periode_laporan_sampai: int = Form(...),
    periode_laporan_next_bulan: int = Form(0),
    wa_api_key: str = Form(...),
    batasi_absen: int = Form(0),
    batas_jam_absen: int = Form(0),
    batas_jam_absen_pulang: int = Form(0),
    multi_lokasi: int = Form(0),
    notifikasi_wa: int = Form(0),
    batasi_hari_izin: int = Form(0),
    jml_hari_izin_max: int = Form(...),
    batas_presensi_lintashari: str = Form(...), # Time string HH:MM:SS
    toleransi_shift_malam_mulai: str = Form(...), # Time string HH:MM:SS
    toleransi_shift_malam_batas: str = Form(...), # Time string HH:MM:SS
    enable_face_block_system: int = Form(0),
    face_block_limit: int = Form(3),
    face_check_liveness_limit: int = Form(3),
    cloud_id: Optional[str] = Form(None),
    api_key: Optional[str] = Form(None),
    domain_email: Optional[str] = Form(None),
    domain_wa_gateway: Optional[str] = Form(None),
    min_supported_version_code: Optional[int] = Form(None),
    latest_version_code: Optional[int] = Form(None),
    update_url: Optional[str] = Form(None),
    update_message: Optional[str] = Form(None),
    logo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    setting = db.query(PengaturanUmum).filter(PengaturanUmum.id == 1).first()
    if not setting:
         raise HTTPException(status_code=404, detail="Settings not found")

    # Update fields
    setting.nama_perusahaan = nama_perusahaan
    setting.alamat = alamat
    setting.telepon = telepon
    setting.total_jam_bulan = total_jam_bulan
    setting.denda = denda
    setting.face_recognition = face_recognition
    setting.periode_laporan_dari = periode_laporan_dari
    setting.periode_laporan_sampai = periode_laporan_sampai
    setting.periode_laporan_next_bulan = periode_laporan_next_bulan
    setting.wa_api_key = wa_api_key
    setting.batasi_absen = batasi_absen
    setting.batas_jam_absen = batas_jam_absen
    setting.batas_jam_absen_pulang = batas_jam_absen_pulang
    setting.multi_lokasi = multi_lokasi
    setting.notifikasi_wa = notifikasi_wa
    setting.batasi_hari_izin = batasi_hari_izin
    setting.jml_hari_izin_max = jml_hari_izin_max
    
    # Parse time string
    try:
        hour, minute, second = map(int, batas_presensi_lintashari.split(':'))
        setting.batas_presensi_lintashari = time(hour, minute, second)
        
        hour_m, minute_m, second_m = map(int, toleransi_shift_malam_mulai.split(':'))
        setting.toleransi_shift_malam_mulai = time(hour_m, minute_m, second_m)
        
        hour_b, minute_b, second_b = map(int, toleransi_shift_malam_batas.split(':'))
        setting.toleransi_shift_malam_batas = time(hour_b, minute_b, second_b)
    except ValueError:
         raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM:SS")

    setting.enable_face_block_system = enable_face_block_system
    setting.face_block_limit = face_block_limit
    setting.face_check_liveness_limit = face_check_liveness_limit
    setting.cloud_id = cloud_id
    setting.api_key = api_key
    setting.domain_email = domain_email
    setting.domain_wa_gateway = domain_wa_gateway
    setting.min_supported_version_code = min_supported_version_code
    setting.latest_version_code = latest_version_code
    setting.update_url = update_url
    setting.update_message = update_message
    setting.updated_at = datetime.now()

    # Handle Logo Upload
    if logo:
        # Generate unique filename
        filename = f"{uuid.uuid4()}{os.path.splitext(logo.filename)[1]}"
        file_path = os.path.join(UPLOAD_DIR, filename)

        # Delete old logo if exists
        if setting.logo:
             old_path = os.path.join(UPLOAD_DIR, setting.logo)
             if os.path.exists(old_path):
                 try:
                     os.remove(old_path)
                 except OSError:
                     pass # Ignore error if file not found
        
        # Save new logo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
            
        setting.logo = filename

    db.commit()
    db.refresh(setting)
    
    return setting
