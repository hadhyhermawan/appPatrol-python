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

    # 0. By DATE EXTRA (Lembur / Double Shift) — Prioritas tertinggi
    try:
        from app.models.models import PresensiJamkerjaBydateExtra
        jk_extra = db.query(PresensiJamkerja)\
            .join(PresensiJamkerjaBydateExtra, PresensiJamkerjaBydateExtra.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .filter(PresensiJamkerjaBydateExtra.nik == nik)\
            .filter(PresensiJamkerjaBydateExtra.tanggal == today)\
            .first()
        if jk_extra:
            return jk_extra
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
    today_date = date.today()

    # 1. Cek status shift aktif (hanya untuk info, TIDAK memblokir list)
    absen_aktif = db.query(Presensi).filter(
        Presensi.nik == nik,
        Presensi.tanggal == today_date,
        Presensi.jam_in != None,
        Presensi.jam_out == None
    ).order_by(Presensi.jam_in.desc()).first()

    # Cek lintas hari (kemarin, belum pulang)
    if not absen_aktif:
        yesterday = today_date - timedelta(days=1)
        absen_aktif = db.query(Presensi).filter(
            Presensi.nik == nik,
            Presensi.tanggal == yesterday,
            Presensi.lintashari == 1,
            Presensi.jam_in != None,
            Presensi.jam_out == None
        ).order_by(Presensi.jam_in.desc()).first()

    # 2. Filter 30 hari terakhir — gunakan WIB
    from datetime import timezone
    WIB = timezone(timedelta(hours=7))
    now_wib = datetime.now(WIB).replace(tzinfo=None)
    filter_from = now_wib - timedelta(days=30)

    # 3. Query 30 hari terakhir per cabang + nama shift dari presensi
    results = db.query(SafetyBriefings, Karyawan.nama_karyawan)\
        .join(Karyawan, SafetyBriefings.nik == Karyawan.nik)\
        .filter(Karyawan.kode_cabang == kode_cabang)\
        .filter(SafetyBriefings.tanggal_jam >= filter_from)\
        .order_by(SafetyBriefings.tanggal_jam.desc())\
        .all()

    data = []
    for sb, nama in results:
        foto_url = f"https://frontend.k3guard.com/api-py/storage/{sb.foto}" if sb.foto else None

        # Batasi nama maksimal 2 kata
        nama_karyawan_truncated = nama
        if nama:
            words = nama.split()
            if len(words) > 2:
                nama_karyawan_truncated = f"{words[0]} {words[1]}..."

        # Cari nama shift dari presensi pada tanggal briefing tersebut
        tgl_briefing = sb.tanggal_jam.date() if sb.tanggal_jam else None
        nama_shift = None
        if tgl_briefing:
            presensi_sb = db.query(Presensi).filter(
                Presensi.nik == sb.nik,
                Presensi.tanggal == tgl_briefing,
            ).first()
            if presensi_sb:
                jk = db.query(PresensiJamkerja).filter(
                    PresensiJamkerja.kode_jam_kerja == presensi_sb.kode_jam_kerja
                ).first()
                if jk:
                    nama_shift = jk.nama_jam_kerja

        data.append({
            "id": sb.id,
            "nik": sb.nik,
            "keterangan": sb.keterangan,
            "foto": sb.foto,
            "foto_url": foto_url,
            "tanggal_jam": str(sb.tanggal_jam),
            "nama_karyawan": nama_karyawan_truncated,
            "kode_cabang": kode_cabang,
            "nama_shift": nama_shift or "Shift"   # fallback jika tidak ada data presensi
        })

    return {
        "status": True,
        "nik": nik,
        "kode_cabang": kode_cabang,
        "shift_aktif": absen_aktif is not None,
        "data": data
    }


@router.post("/safetybriefing/store")
async def store_safety_briefing(
    keterangan: str = Form(...),
    foto: UploadFile = File(...),
    tanggal_jam: str = Form(None),  # WIB timestamp dari device Android
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
        
    # ==================================================================
    # 4. Validasi waktu: pastikan SEKARANG masih dalam window shift
    # Karyawan lupa absen pulang dari shift lama → lewat dari end_dt
    # Toleransi 30 menit setelah shift berakhir
    # ==================================================================
    from datetime import timezone
    WIB = timezone(timedelta(hours=7))
    now_wib = datetime.now(WIB).replace(tzinfo=None)

    # Toleransi 30 menit setelah jam_pulang
    shift_deadline = end_dt + timedelta(minutes=30)

    # Hitung window mulai: 2 jam sebelum jam_masuk (early bird)
    shift_start_window = start_dt - timedelta(hours=2)

    if not (shift_start_window <= now_wib <= shift_deadline):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={
            "status": False,
            "message": f"Di luar jam shift aktif. Shift: {jam_kerja.jam_masuk.strftime('%H:%M')}–{jam_kerja.jam_pulang.strftime('%H:%M')}. Silakan lakukan absen pulang terlebih dahulu.",
            "shift_mulai": str(jam_kerja.jam_masuk),
            "shift_selesai": str(jam_kerja.jam_pulang)
        })

    # ==================================================================
    # 5. Check Absen Masuk yang AKTIF (sudah masuk, belum absen pulang)
    # ==================================================================
    # Tentukan rentang tanggal check — pertimbangkan shift lintas hari
    check_dates = [today_date]
    if start_dt.date() != end_dt.date():            # shift lintas hari
        check_dates.append(today_date - timedelta(days=1))

    absen = db.query(Presensi).filter(
        Presensi.nik == nik,
        Presensi.status == 'h',
        Presensi.kode_jam_kerja == jam_kerja.kode_jam_kerja,
        Presensi.tanggal.in_(check_dates),
        Presensi.jam_in != None,
        Presensi.jam_out == None
    ).order_by(Presensi.jam_in.desc()).first()

    if not absen:
        # Fallback: tanpa kode_jam_kerja spesifik, tapi tetap belum pulang
        absen = db.query(Presensi).filter(
            Presensi.nik == nik,
            Presensi.status == 'h',
            Presensi.tanggal.in_(check_dates),
            Presensi.jam_in != None,
            Presensi.jam_out == None
        ).order_by(Presensi.jam_in.desc()).first()

    if not absen:
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
        
    # 7. Simpan — gunakan WIB
    from datetime import timezone
    WIB = timezone(timedelta(hours=7))
    now_wib = datetime.now(WIB).replace(tzinfo=None)

    # Prioritas: tanggal_jam dari Android (sudah WIB), fallback ke server WIB
    if tanggal_jam:
        try:
            tanggal_jam_dt = datetime.strptime(tanggal_jam, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            tanggal_jam_dt = now_wib
    else:
        tanggal_jam_dt = now_wib

    new_sb = SafetyBriefings(
        nik=nik,
        keterangan=keterangan,
        foto=foto_path,
        tanggal_jam=tanggal_jam_dt,
        created_at=now_wib,
        updated_at=now_wib
    )
    
    db.add(new_sb)
    db.commit()
    db.refresh(new_sb)
    
    foto_url = f"https://frontend.k3guard.com/api-py/storage/{new_sb.foto}" if new_sb.foto else None

    # Batasi nama maksimal 2 kata
    nama_karyawan_truncated = karyawan.nama_karyawan
    if nama_karyawan_truncated:
        words = nama_karyawan_truncated.split()
        if len(words) > 2:
            nama_karyawan_truncated = f"{words[0]} {words[1]}..."

    return {
        "status": True,
        "message": "Safety briefing berhasil dicatat",
        "data": {
            "id": new_sb.id,
            "nik": new_sb.nik,
            "foto": new_sb.foto,
            "foto_url": foto_url,
            "keterangan": new_sb.keterangan,
            "tanggal_jam": str(new_sb.tanggal_jam),
            "created_at": str(new_sb.created_at) if new_sb.created_at else None,
            "updated_at": str(new_sb.updated_at) if new_sb.updated_at else None,
            "nama_karyawan": nama_karyawan_truncated,
            "kode_cabang": kode_cabang
        }
    }
