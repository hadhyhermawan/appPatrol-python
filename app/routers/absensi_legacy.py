from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from app.database import get_db
from app.routers.auth_legacy import get_current_user_nik
from app.models.models import Presensi, PresensiJamkerja, Karyawan, PengaturanUmum
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

def determine_jam_kerja_hari_ini(db: Session, nik: str, today: date, now_wib: datetime):
    from app.models.models import SetJamKerjaByDate, SetJamKerjaByDay, PresensiJamkerja, Karyawan, PresensiJamkerjaBydept, PresensiJamkerjaBydateExtra
    
    jam_kerja_obj = None
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

    # Determine Jam Kerja
    if presensi:
        # User already clocked in, use the recorded schedule
        jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == presensi.kode_jam_kerja).first()
    else:
        # Not clocked in yet, find today's schedule
        
        # 0. By Date Extra (Highest Priority Override)
        by_date_extra = db.query(PresensiJamkerjaBydateExtra).filter(PresensiJamkerjaBydateExtra.nik == nik, PresensiJamkerjaBydateExtra.tanggal == today).first()
        if by_date_extra:
             jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == by_date_extra.kode_jam_kerja).first()

        # 1. By Date
        if not jam_kerja_obj:
            by_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.nik == nik, SetJamKerjaByDate.tanggal == today).first()
            if by_date:
                jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == by_date.kode_jam_kerja).first()
                
        if not jam_kerja_obj:
            # 2. By Day
            days_map = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
            day_name = days_map[now_wib.weekday()]
            
            by_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik, SetJamKerjaByDay.hari == day_name).first()
            if by_day:
                jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == by_day.kode_jam_kerja).first()
            else:
                karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
                if karyawan and karyawan.kode_dept:
                    try:
                        from app.models.models import PresensiJamkerjaByDeptDetail
                        dept_header = db.query(PresensiJamkerjaBydept).filter(
                            PresensiJamkerjaBydept.kode_dept == karyawan.kode_dept,
                            PresensiJamkerjaBydept.kode_cabang == karyawan.kode_cabang
                        ).first()
                        if dept_header:
                            dept_detail = db.query(PresensiJamkerjaByDeptDetail).filter(
                                PresensiJamkerjaByDeptDetail.kode_jk_dept == dept_header.kode_jk_dept,
                                PresensiJamkerjaByDeptDetail.hari == day_name
                            ).first()
                            if dept_detail and dept_detail.kode_jam_kerja:
                                jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == dept_detail.kode_jam_kerja).first()
                    except Exception as e:
                        pass

                # 4. Default User
                if not jam_kerja_obj and karyawan and karyawan.kode_jadwal:
                     jam_kerja_obj = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == karyawan.kode_jadwal).first()

    return jam_kerja_obj, presensi

@router.get("/hariini")
async def get_presensi_hari_ini(
    nik: str = Depends(get_current_user_nik),
    db: Session = Depends(get_db)
):
    # Use WIB Timezone
    now_wib = datetime.now(WIB)
    today = now_wib.date()
    
    # Get general settings early
    from app.models.models import Karyawan, Cabang, KaryawanWajah, PengaturanUmum
    setting = db.query(PengaturanUmum).first()
    
    # Logic Toleransi Awal (Early Check-In / Shift Malam Next Day)
    from datetime import time
    toleransi_mulai = setting.toleransi_shift_malam_mulai if setting and setting.toleransi_shift_malam_mulai else time(20, 0)
    toleransi_batas = setting.toleransi_shift_malam_batas if setting and setting.toleransi_shift_malam_batas else time(6, 0)
    
    if now_wib.time() >= toleransi_mulai:
        # Pastikan tidak ada shift hari ini yang masih gantung (belum absen pulang)
        active_today = db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today, Presensi.jam_out == None).first()
        if not active_today:
            tomorrow = today + timedelta(days=1)
            jam_kerja_tmrw, _ = determine_jam_kerja_hari_ini(db, nik, tomorrow, now_wib)
            # Jika besok ada shift yang dimulai dini hari,
            # maka anggap "hari ini" adalah shift besok tersebut agar bisa absen.
            if jam_kerja_tmrw and jam_kerja_tmrw.jam_masuk <= toleransi_batas:
                today = tomorrow
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if not karyawan:
        raise HTTPException(404, "Data Karyawan tidak ditemukan")
        
    jam_kerja_obj, presensi = determine_jam_kerja_hari_ini(db, nik, today, now_wib)

    # Get Cabang Info
    cabang = None
    if karyawan.kode_cabang:
        cabang = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
        
    # Check Face Registered
    wajah_count = db.query(KaryawanWajah).filter(KaryawanWajah.nik == nik).count()
    wajah_terdaftar = 1 if wajah_count > 0 else 0
    
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
        "status": str(presensi.status).upper() if presensi and presensi.status else ("H" if presensi else "A"),
        "foto_in": presensi.foto_in if presensi else None,
        "foto_out": presensi.foto_out if presensi else None,
        "lokasi_in": presensi.lokasi_in if presensi else None,
        "lokasi_out": presensi.lokasi_out if presensi else None,
        "wajah_terdaftar": wajah_terdaftar,
        
        # Logic Flags
        "absen_masuk_selesai": True if (presensi and presensi.jam_in) or (presensi and presensi.status and presensi.status.lower() != 'h' and presensi.status.lower() != 'a') else False,
        "absen_pulang_selesai": True if (presensi and presensi.jam_out) or (presensi and presensi.status and presensi.status.lower() != 'h' and presensi.status.lower() != 'a') else False,
        "tombol_enabled": True if not (str(karyawan.lock_jam_kerja) == '1' and not jam_kerja_obj and not presensi) else False,
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

    from app.models.models import PengaturanUmum
    setting = db.query(PengaturanUmum).first()
    
    # Logic Toleransi Awal (Early Check-In / Shift Malam Next Day)
    from datetime import time
    toleransi_mulai = setting.toleransi_shift_malam_mulai if setting and setting.toleransi_shift_malam_mulai else time(20, 0)
    toleransi_batas = setting.toleransi_shift_malam_batas if setting and setting.toleransi_shift_malam_batas else time(6, 0)

    if is_masuk and now.time() >= toleransi_mulai:
        # Jika malam hari mau absen masuk, cek apakah shift hari ini masih ada yg belum tutup
        active_today = db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today, Presensi.jam_out == None).first()
        if not active_today:
            tomorrow = today + timedelta(days=1)
            jam_kerja_tmrw, _ = determine_jam_kerja_hari_ini(db, nik, tomorrow, now)
            # Jika besok ada jadwal dini hari, kita ubah object today menjadi tomorrow
            if jam_kerja_tmrw and jam_kerja_tmrw.jam_masuk <= toleransi_batas:
                today = tomorrow
    
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
            if existing.status and existing.status.lower() not in ['h', 'a']:
                raise HTTPException(status_code=400, detail=f"Anda tidak dapat absen, status hari ini: {existing.status.upper()}")
            raise HTTPException(status_code=400, detail="Anda sudah absen masuk hari ini.")
        
        # TENTUKAN SCHEDULE TERBAIK (JIKA KOSONG/NS DARI FRONTEND)
        jk = None
        used_kode_jam_kerja = kode_jam_kerja if kode_jam_kerja else 'NS'
        if used_kode_jam_kerja != 'NS' and used_kode_jam_kerja != '':
            jk = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == used_kode_jam_kerja).first()

        if not jk:
             # FALLBACK: HITUNG SENDIRI JADWAL HARI INI SECARA PINTAR
             jam_kerja_obj, _ = determine_jam_kerja_hari_ini(db, nik, today, now)
             if jam_kerja_obj:
                 jk = jam_kerja_obj
                 used_kode_jam_kerja = jk.kode_jam_kerja
             else:
                 karyawan_check = db.query(Karyawan).filter(Karyawan.nik == nik).first()
                 if karyawan_check and str(karyawan_check.lock_jam_kerja) == '1':
                     raise HTTPException(400, "Anda tidak memiliki jadwal kerja hari ini dan status jadwal Anda Terkunci. Silakan hubungi Admin.")
                     
                 # Jika tidak di-lock, fallback ke entry shift pertama sebagai default
                 jk = db.query(PresensiJamkerja).first()
                 if not jk:
                      raise HTTPException(500, "Master Jam Kerja kosong.")
                 used_kode_jam_kerja = jk.kode_jam_kerja
        
        if not jk:
            jk = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == used_kode_jam_kerja).first()
            
        # Logic Kunci Jam Kerja (Bounds) untuk Masuk
        karyawan_check = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if karyawan_check and str(karyawan_check.lock_jam_kerja) == '1' and setting and str(setting.batasi_absen) == '1' and jk:
            batas_absen = int(setting.batas_jam_absen) if setting.batas_jam_absen else 0
            jadwal_masuk_str = f"{today.strftime('%Y-%m-%d')} {jk.jam_masuk.strftime('%H:%M:%S')}"
            jadwal_masuk = datetime.strptime(jadwal_masuk_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=WIB)
            batas_akhir_masuk = jadwal_masuk + timedelta(hours=batas_absen)
            batas_awal_masuk = jadwal_masuk - timedelta(hours=3) # Allow 3 hours early max
            
            if now > batas_akhir_masuk:
                raise HTTPException(403, "Batas waktu absen masuk berakhir.")
            if now < batas_awal_masuk:
                raise HTTPException(403, "Belum waktunya absen masuk.")
                
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
             
        # Logic Kunci Jam Kerja (Bounds) untuk Pulang
        karyawan_check = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if karyawan_check and str(karyawan_check.lock_jam_kerja) == '1' and setting and str(setting.batasi_absen) == '1':
            jk = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == presensi.kode_jam_kerja).first()
            if jk:
                batas_absen_pulang = int(setting.batas_jam_absen_pulang) if setting.batas_jam_absen_pulang else 0
                
                # Konversi timezone safe timestamp untuk jadwal pulang
                jadwal_pulang_str = f"{presensi.tanggal.strftime('%Y-%m-%d')} {jk.jam_pulang.strftime('%H:%M:%S')}"
                jadwal_pulang = datetime.strptime(jadwal_pulang_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=WIB)
                
                if str(jk.lintashari) == '1':
                    jadwal_pulang = jadwal_pulang + timedelta(days=1)
                    
                batas_akhir_pulang = jadwal_pulang + timedelta(hours=batas_absen_pulang)
                
                if now < jadwal_pulang:
                    raise HTTPException(403, f"Belum waktunya absen pulang. Anda baru bisa pulang pukul {jadwal_pulang.strftime('%H:%M WIB')} atau setelahnya.")
                    
                if now > batas_akhir_pulang:
                    raise HTTPException(403, "Batas waktu absen pulang berakhir.")
                    
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

@router.post("/request-bypass-radius")
async def request_bypass_radius(
    lokasi: str = Form(None),
    keterangan: str = Form(None),
    nik: str = Depends(get_current_user_nik),
    db: Session = Depends(get_db)
):
    from app.models.models import SecurityReports, Karyawan, KaryawanDevices, Cabang
    from firebase_admin import messaging
    
    # 1. Pastikan belum ada request pending
    existing = db.query(SecurityReports).filter(
        SecurityReports.nik == nik,
        SecurityReports.type == 'RADIUS_BYPASS',
        SecurityReports.status_flag == 'pending'
    ).first()
    
    if existing:
        return {"status": False, "message": "Anda sudah mengajukan izin yang saat ini sedang menunggu persetujuan."}
        
    latitude = None
    longitude = None
    if lokasi and ',' in lokasi:
        try:
            latitude = float(lokasi.split(',')[0].strip())
            longitude = float(lokasi.split(',')[1].strip())
        except:
            pass

    from app.models.models import LoginLogs
    ll = db.query(LoginLogs).filter(LoginLogs.user_id == user.id).order_by(LoginLogs.id.desc()).first()
    device_mdl = ll.device if ll else None
    ip_addr = ll.ip if ll else None

    report = SecurityReports(
        user_id=user.id,
        type='RADIUS_BYPASS',
        detail=f"Meminta izin absen luar tapak. Alasan: {keterangan or 'GPS tidak akurat'}.",
        nik=nik,
        latitude=latitude,
        longitude=longitude,
        status_flag='pending',
        device_model=device_mdl,
        ip_address=ip_addr,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(report)
    db.commit()
    
    # 2. Eskalasi ke Danru/Admin
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if karyawan and karyawan.kode_cabang:
        # Kirim notif ke seluruh Danru/Admin di Cabang tersebut
        target_karyawans = db.query(Karyawan.nik).filter(
             Karyawan.kode_cabang == karyawan.kode_cabang,
             Karyawan.nik != nik
        ).all()
        target_niks = [r[0] for r in target_karyawans]
        
        if target_niks:
            devices = db.query(KaryawanDevices).filter(KaryawanDevices.nik.in_(target_niks)).all()
            tokens = [d.fcm_token for d in devices if d.fcm_token]
            
            if tokens:
                try:
                    nama_pemohon = karyawan.nama_karyawan or nik
                    cabang_info = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
                    nama_cabang = cabang_info.nama_cabang if cabang_info else "Cabang"

                    msg = messaging.MulticastMessage(
                        notification=messaging.Notification(
                            title="Izin Absen Luar Tapak",
                            body=f"Personel {nama_pemohon} meminta bypass radius absen di Area {nama_cabang}."
                        ),
                        data={
                            "type": "SECURITY_ALERT_BYPASS",
                            "subtype": "RADIUS_BYPASS",
                            "nik_pemohon": nik,
                            "nama_pemohon": nama_pemohon 
                        },
                        tokens=tokens[:500],
                        android=messaging.AndroidConfig(priority='high')
                    )
                    messaging.send_each_for_multicast(msg)
                except Exception as e:
                    pass

    return {"status": True, "message": "Izin absen luar tapak berhasil diajukan. Silakan tunggu persetujuan Atasan."}
