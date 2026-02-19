from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.database import get_db
from app.routers.auth_legacy import get_current_user_nik
from app.models.models import Presensi, PresensiJamkerja
from datetime import datetime, date, timedelta
import shutil
import os
import uuid
import pytz

router = APIRouter(
    prefix="/api/android/absensi",
    tags=["Absensi Legacy"],
    responses={404: {"description": "Not found"}},
)

# Use Laravel's storage path for compatibility with existing admin panel
STORAGE_PATH = "/var/www/appPatrol/storage/app/public/uploads/absensi"
os.makedirs(STORAGE_PATH, exist_ok=True)

# Set Timezone
WIB = pytz.timezone('Asia/Jakarta')

@router.get("/hariini")
async def get_presensi_hari_ini(
    nik: str = Depends(get_current_user_nik),
    db: Session = Depends(get_db)
):
    # Use WIB Timezone
    now_wib = datetime.now(WIB)
    today = now_wib.date()
    
    # 1. Get Employee Data & Shift Schedule
    # Correct models import verified via debug script
    from app.models.models import SetJamKerjaByDate, SetJamKerjaByDay, PresensiJamkerja, Karyawan, Cabang, KaryawanWajah, PengaturanUmum, PresensiJamkerjaBydept, PresensiJamkerjaBydateExtra
    
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if not karyawan:
        raise HTTPException(404, "Data Karyawan tidak ditemukan")
        
    # Schedule Logic (Priority: Presensi > Date Extra > Date > Day > Dept Default > User Default)
    jam_kerja_obj = None
    
    # Check Presensi first to see if user already clocked in with specific schedule
    presensi = db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today).first()
    
    # Logic Lintas Hari: Check if yesterday's shift is still ongoing
    if not presensi:
        yesterday = today - timedelta(days=1)
        presensi_yesterday = db.query(Presensi).filter(
            Presensi.nik == nik, 
            Presensi.tanggal == yesterday,
            Presensi.lintashari == 1,
            Presensi.jam_out == None
        ).first()
        if presensi_yesterday:
            presensi = presensi_yesterday
            # If tracking yesterday's shift, stick to that shift
            
    # Determine Jam Kerja
    if presensi:
        # User already clocked in, use the recorded schedule
        jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == presensi.kode_jam_kerja).first()
    else:
        # Not clocked in yet, find today's schedule
        
        # 0. By Date Extra (PresensiJamkerjaBydateExtra) - Highest Priority Override
        by_date_extra = db.query(PresensiJamkerjaBydateExtra).filter(PresensiJamkerjaBydateExtra.nik == nik, PresensiJamkerjaBydateExtra.tanggal == today).first()
        if by_date_extra:
             jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == by_date_extra.kode_jam_kerja).first()

        # 1. By Date (SetJamKerjaByDate -> table presensi_jamkerja_bydate)
        if not jam_kerja_obj:
            by_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today).first()
            if by_date:
                jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == by_date.kode_jam_kerja).first()
                
        if not jam_kerja_obj:
            # 2. By Day (SetJamKerjaByDay -> table presensi_jamkerja_byday)
            days_map = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            day_name = days_map[now_wib.weekday()]
            
            by_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == day_name).first()
            if by_day:
                jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == by_day.kode_jam_kerja).first()
            else:
                # 3. Dept Default (PresensiJamkerjaBydept & Detail)
                if karyawan.kode_dept:
                    try:
                        from app.models.models import PresensiJamkerjaByDeptDetail
                        
                        # Logic: Find Dept Schedule -> Find Detail by Day
                        # Join: presensi_jamkerja_bydept -> detail -> presensi_jamkerja
                        
                        # Note: Using join directly on models/tables
                        # We need PresensiJamkerjaBydept (header) + t_detail + PresensiJamkerja
                        
                        # Since header is needed to match DEPT & CABANG
                        dept_header = db.query(PresensiJamkerjaBydept).filter(
                            PresensiJamkerjaBydept.kode_dept == karyawan.kode_dept,
                            PresensiJamkerjaBydept.kode_cabang == karyawan.kode_cabang
                        ).first()
                        
                        if dept_header:
                            # Find detail for today (day_name)
                            dept_detail = db.query(PresensiJamkerjaByDeptDetail).filter(
                                PresensiJamkerjaByDeptDetail.kode_jk_dept == dept_header.kode_jk_dept,
                                PresensiJamkerjaByDeptDetail.hari == day_name
                            ).first()
                            
                            if dept_detail:
                                # dept_detail is now an ORM object
                                
                                # Let's query JamKerja based on found code
                                jk_code = dept_detail.kode_jam_kerja
                                     
                                if jk_code:
                                    jam_kerja_obj = db.query(PresensiJamkerja).filter(
                                        PresensiJamkerja.kode_jam_kerja == jk_code
                                    ).first()
                    except Exception as e:

                        # Log error but don't crash. Fallback to next priority.
                        print(f"Error in Dept Default Schedule Logic: {e}")
                        pass


                # 4. Default User (Karyawan.kode_jadwal)
                if not jam_kerja_obj:
                     # Check Karyawan.kode_jadwal first (Default Schedule)
                     if karyawan.kode_jadwal:
                         jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == karyawan.kode_jadwal).first()
                     # Fallback to Karyawan.kode_jam_kerja if column exists? Most likely kode_jadwal is the one.


    # Get Cabang Info
    cabang = None
    if karyawan.kode_cabang:
        cabang = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
        
    # Check Face Registered
    wajah_count = db.query(KaryawanWajah).filter(KaryawanWajah.nik == nik).count()
    wajah_terdaftar = 1 if wajah_count > 0 else 0
    
    # Check General Settings
    setting = db.query(PengaturanUmum).first()
    face_recognition = bool(setting.face_recognition) if setting else False
    
    # Construct Flat Data
    data = {
        "nik": karyawan.nik,
        "nama_karyawan": karyawan.nama_karyawan,
        "kode_dept": karyawan.kode_dept,
        "kode_cabang": karyawan.kode_cabang,
        "nama_cabang": cabang.nama_cabang if cabang else None,
        "lokasi_cabang": cabang.lokasi_cabang if cabang else None,
        "radius_cabang": cabang.radius_cabang if cabang else 30,
        "tanggal_presensi": today.strftime("%Y-%m-%d"),
        "nama_jam_kerja": jam_kerja_obj.nama_jam_kerja if jam_kerja_obj else "-",
        "kode_jam_kerja": jam_kerja_obj.kode_jam_kerja if jam_kerja_obj else None,
        "jam_masuk": str(jam_kerja_obj.jam_masuk) if jam_kerja_obj else None,
        "jam_pulang": str(jam_kerja_obj.jam_pulang) if jam_kerja_obj else None,
        
        # Presensi Data
        "jam_in": presensi.jam_in.strftime("%H:%M:%S") if presensi and presensi.jam_in else None,
        "jam_out": presensi.jam_out.strftime("%H:%M:%S") if presensi and presensi.jam_out else None,
        "status": "H" if presensi else "A",
        "foto_in": presensi.foto_in if presensi else None,
        "foto_out": presensi.foto_out if presensi else None,
        "lokasi_in": presensi.lokasi_in if presensi else None,
        "lokasi_out": presensi.lokasi_out if presensi else None,
        "wajah_terdaftar": wajah_terdaftar,
        
        # Logic Flags
        "absen_masuk_selesai": True if (presensi and presensi.jam_in) else False,
        "absen_pulang_selesai": True if (presensi and presensi.jam_out) else False,
        "tombol_enabled": True, # Logic handled by app usually, but we enable by default
        "lock_location": True if str(karyawan.lock_location) == '1' else False,
        "lock_jam_kerja": True if str(karyawan.lock_jam_kerja) == '1' else False,
        "face_recognition": face_recognition
    }
    
    return {
        "status": True,
        "message": "Data Presensi Hari Ini",
        "data": data
    }


@router.post("/absen")
async def absen(
    image: UploadFile = File(...),
    status: str = Form(...), # 'masuk' or 'pulang' per logic API Android
    lokasi: str = Form(...),
    kode_jam_kerja: str | None = Form(None),
    nik: str = Depends(get_current_user_nik),
    db: Session = Depends(get_db)
):
    now = datetime.now(WIB)
    today = now.date()
    
    # Check status string. Case insensitive.
    status_lower = status.lower().strip()
    is_masuk = status_lower in ['masuk', 'in', '1']
    is_pulang = status_lower in ['pulang', 'out', '2']
    
    if not is_masuk and not is_pulang:
         raise HTTPException(status_code=400, detail=f"Status absen tidak valid: {status}")
    
    # 1. Save Image
    # Filename format: {nik}-{date}-{in/out}.ext (Match Laravel)
    in_out_str = "in" if is_masuk else "out"
    ext_split = image.filename.split('.')
    ext = ext_split[-1] if len(ext_split) > 1 else 'png' # Default png
    
    filename = f"{nik}-{today.strftime('%Y-%m-%d')}-{in_out_str}.{ext}"
    file_path = os.path.join(STORAGE_PATH, filename)
    
    try:
        # Reset pointer just in case and read async
        await image.seek(0)
        content = await image.read()
        with open(file_path, "wb") as buffer:
            buffer.write(content)
            
    except Exception as e:
        raise HTTPException(500, f"Gagal menyimpan foto: {str(e)}")
        
    # Save only filename to DB (Laravel Accessor handles the path)
    db_image_path = filename 
    message = ""

    # 2. Logic Absen Masuk
    if is_masuk:
        # Check existing
        existing = db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today).first()
        if existing:
            # If exists and lintashari=1 (yesterday shift), maybe allowed? 
            # But usually 'masuk' means new shift.
            raise HTTPException(status_code=400, detail="Anda sudah absen masuk hari ini.")
        
        # Determine Kode Jam Kerja
        used_kode_jam_kerja = kode_jam_kerja if kode_jam_kerja else 'NS'
        
        # Check Jam Kerja Model
        jk = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == used_kode_jam_kerja).first()
        if not jk:
             # Fallback if provided invalid or 'NS' missing
             jk = db.query(PresensiJamkerja).first()
             if not jk:
                  raise HTTPException(500, "Master Jam Kerja kosong.")
             used_kode_jam_kerja = jk.kode_jam_kerja
        
        lintas_hari_val = 0
        # Check char '1' in DB
        if str(jk.lintashari) == '1':
             lintas_hari_val = 1
             
        new_presensi = Presensi(
            nik=nik,
            tanggal=today,
            kode_jam_kerja=used_kode_jam_kerja,
            status='H', # Hadir
            lintashari=lintas_hari_val,
            jam_in=now,
            foto_in=db_image_path,
            lokasi_in=lokasi,
            created_at=now,
            updated_at=now
        )
        db.add(new_presensi)
        db.commit()
        db.refresh(new_presensi)
        message = "Berhasil Absen Masuk"
        
    # 3. Logic Absen Pulang
    elif is_pulang:
        # Find presensi to clock out
        presensi = db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today).first()
        
        # Lintas Hari Logic: Check yesterday if user clocked in yesterday on a night shift
        if not presensi:
            yesterday = today - timedelta(days=1)
            presensi_yesterday = db.query(Presensi).filter(
                Presensi.nik == nik, 
                Presensi.tanggal == yesterday,
                Presensi.lintashari == 1,
                Presensi.jam_out == None
            ).first()
            
            if presensi_yesterday:
                presensi = presensi_yesterday
        
        if not presensi:
             raise HTTPException(status_code=400, detail="Belum absen masuk, tidak bisa absen pulang.")
             
        if presensi.jam_out:
             raise HTTPException(status_code=400, detail="Anda sudah absen pulang sebelumnya.")
             
        presensi.jam_out = now
        presensi.foto_out = db_image_path
        presensi.lokasi_out = lokasi
        presensi.updated_at = now
        
        db.commit()
        message = "Berhasil Absen Pulang"

    return {
        "status": True,
        "message": message,
        # Return filename or full url if needed by Android immediately? Usually just success message.
    }
