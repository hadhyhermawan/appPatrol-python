from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func, extract
from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import (
    Presensi, PresensiJamkerja, Userkaryawan, Karyawan, 
    SetJamKerjaByDay, SetJamKerjaByDate
)
# Note: Detailsetjamkerjabydept imports might be tricky if not in models.py, 
# but for basic roster/regular schedule logic, Date & Day tables are primary.

from datetime import datetime, date, timedelta
import calendar

router = APIRouter(
    prefix="/api/android/jamkerja",
    tags=["Jam Kerja Legacy"],
    responses={404: {"description": "Not found"}},
)

@router.get("/bulanan")
async def get_jadwal_bulanan(
    month: int = Query(..., description="Bulan (1-12)"),
    year: int = Query(..., description="Tahun (YYYY)"),
    current_user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Get Karyawan Info
    user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.id_user == current_user.id).first()
    if not user_karyawan:
        return {"status": False, "message": "Data Karyawan Tidak Ditemukan"}
        
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user_karyawan.nik).first()
    if not karyawan:
        return {"status": False, "message": "Data Karyawan Tidak Ditemukan"}
        
    nik = karyawan.nik

    # 2. Prepare Date Range
    try:
        _, last_day = calendar.monthrange(year, month)
        start_date = date(year, month, 1)
        end_date = date(year, month, last_day)
    except ValueError:
        return {"status": False, "message": "Bulan atau Tahun tidak valid."}

    # 3. Fetch Roster (Specific Date Schedule)
    # Join SetJamKerjaByDate with PresensiJamkerja
    roster_records = db.query(SetJamKerjaByDate, PresensiJamkerja)\
        .join(PresensiJamkerja, SetJamKerjaByDate.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
        .filter(SetJamKerjaByDate.nik == nik)\
        .filter(extract('month', SetJamKerjaByDate.tanggal) == month)\
        .filter(extract('year', SetJamKerjaByDate.tanggal) == year)\
        .all()
        
    roster_map = {r.SetJamKerjaByDate.tanggal: r.PresensiJamkerja for r in roster_records}

    # 4. Fetch Regular Schedule (By Day Name)
    # Join SetJamKerjaByDay with PresensiJamkerja
    regular_records = db.query(SetJamKerjaByDay, PresensiJamkerja)\
        .join(PresensiJamkerja, SetJamKerjaByDay.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
        .filter(SetJamKerjaByDay.nik == nik)\
        .all()
        
    # Map 'Senin' -> JamKerja obj
    regular_map = {r.SetJamKerjaByDay.hari: r.PresensiJamkerja for r in regular_records}

    # 5. Fetch Actual Presensi (Realisasi)
    presensi_records = db.query(Presensi).filter(
        Presensi.nik == nik,
        extract('month', Presensi.tanggal) == month,
        extract('year', Presensi.tanggal) == year
    ).all()
    
    presensi_map = {p.tanggal: p for p in presensi_records}

    # 6. Generate Calendar Loop
    jadwal_full = []
    
    # Translate Python weekday (0=Mon) to Indo Day Name
    days_map = {
        0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'
    }
    
    curr = start_date
    while curr <= end_date:
        day_str = curr.strftime("%Y-%m-%d")
        day_name = days_map[curr.weekday()]
        
        # Default Item Structure (Libur)
        item = {
            "tanggal": day_str,
            "hari": day_name,
            "kode_jam_kerja": "LIBR",
            "nama_jam_kerja": "Libur",
            "jam_masuk": None, # Should be string or null
            "jam_pulang": None,
            "is_roster": False,
            "jam_absen_masuk": None,
            "jam_absen_pulang": None
        }
        
        # Logic Priority: Roster -> Regular
        jk_obj = None
        is_roster = False
        
        if curr in roster_map:
            jk_obj = roster_map[curr]
            is_roster = True
        elif day_name in regular_map:
            jk_obj = regular_map[day_name]
            is_roster = False
            
        if jk_obj:
            item["kode_jam_kerja"] = jk_obj.kode_jam_kerja
            item["nama_jam_kerja"] = jk_obj.nama_jam_kerja
            item["jam_masuk"] = str(jk_obj.jam_masuk) if jk_obj.jam_masuk else None
            item["jam_pulang"] = str(jk_obj.jam_pulang) if jk_obj.jam_pulang else None
            item["is_roster"] = is_roster
            
        # Realisasi Presensi
        if curr in presensi_map:
            p = presensi_map[curr]
            # Format time HH:MM:SS
            item["jam_absen_masuk"] = str(p.jam_in) if p.jam_in else None
            item["jam_absen_pulang"] = str(p.jam_out) if p.jam_out else None
            
        jadwal_full.append(item)
        curr += timedelta(days=1)

    return {
        "status": True,
        "message": "Jadwal bulanan berhasil diambil",
        "data": jadwal_full
    }
