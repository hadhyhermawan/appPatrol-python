from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, func, extract
from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import (
    Presensi, PresensiJamkerja, Userkaryawan, Karyawan, 
    SetJamKerjaByDay, SetJamKerjaByDate, PresensiJamkerjaBydept, PresensiJamkerjaBydeptDetail, PresensiJamkerjaBydateExtra
)
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

    # 3. Cache all Jam Kerja master data
    jamkerjas = db.query(PresensiJamkerja).all()
    jk_map = {jk.kode_jam_kerja: jk for jk in jamkerjas}

    # 4. Fetch User Priorities
    # Priority 0: Extra Date
    extra_date_records = db.query(PresensiJamkerjaBydateExtra).filter(
        PresensiJamkerjaBydateExtra.nik == nik,
        extract('month', PresensiJamkerjaBydateExtra.tanggal) == month,
        extract('year', PresensiJamkerjaBydateExtra.tanggal) == year
    ).all()
    extra_date_map = {r.tanggal: r.kode_jam_kerja for r in extra_date_records}

    # Priority 1: Roster Date
    roster_records = db.query(SetJamKerjaByDate).filter(
        SetJamKerjaByDate.nik == nik,
        extract('month', SetJamKerjaByDate.tanggal) == month,
        extract('year', SetJamKerjaByDate.tanggal) == year
    ).all()
    roster_map = {r.tanggal: r.kode_jam_kerja for r in roster_records}

    # Priority 2: Regular Day
    regular_records = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik).all()
    regular_map = {r.hari: r.kode_jam_kerja for r in regular_records}

    # Priority 3: Dept Day
    dept_map = {}
    if karyawan.kode_dept:
        dept_header = db.query(PresensiJamkerjaBydept).filter(
            PresensiJamkerjaBydept.kode_dept == karyawan.kode_dept,
            PresensiJamkerjaBydept.kode_cabang == karyawan.kode_cabang
        ).first()
        if dept_header:
            dept_details = db.query(PresensiJamkerjaBydeptDetail).filter(
                PresensiJamkerjaBydeptDetail.kode_jk_dept == dept_header.kode_jk_dept
            ).all()
            dept_map = {d.hari: d.kode_jam_kerja for d in dept_details}

    # 5. Fetch Actual Presensi (Realisasi)
    presensi_records = db.query(Presensi).filter(
        Presensi.nik == nik,
        extract('month', Presensi.tanggal) == month,
        extract('year', Presensi.tanggal) == year
    ).all()
    
    presensi_map = {p.tanggal: p for p in presensi_records}

    # 5.5 Fetch Izin
    from app.models.models import PresensiIzinabsen, PresensiIzindinas, PresensiIzinsakit, PresensiIzincuti
    from sqlalchemy import and_

    izin_map = {}
    
    def populate_izin(records, status_code):
        for r in records:
            if str(r.status) != '1': continue
            curr_izin = r.dari
            while curr_izin <= r.sampai:
                izin_map[curr_izin] = status_code
                curr_izin += timedelta(days=1)
                
    izin_absens = db.query(PresensiIzinabsen).filter(and_(PresensiIzinabsen.nik == nik, PresensiIzinabsen.dari <= end_date, PresensiIzinabsen.sampai >= start_date)).all()
    populate_izin(izin_absens, 'I')
    
    izin_sakits = db.query(PresensiIzinsakit).filter(and_(PresensiIzinsakit.nik == nik, PresensiIzinsakit.dari <= end_date, PresensiIzinsakit.sampai >= start_date)).all()
    populate_izin(izin_sakits, 'S')
    
    izin_cutis = db.query(PresensiIzincuti).filter(and_(PresensiIzincuti.nik == nik, PresensiIzincuti.dari <= end_date, PresensiIzincuti.sampai >= start_date)).all()
    populate_izin(izin_cutis, 'C')
    
    izin_dinas = db.query(PresensiIzindinas).filter(and_(PresensiIzindinas.nik == nik, PresensiIzindinas.dari <= end_date, PresensiIzindinas.sampai >= start_date)).all()
    populate_izin(izin_dinas, 'DL')

    # 6. Generate Calendar Loop
    jadwal_full = []
    
    # Translate Python weekday (0=Mon) to Indo Day Name
    days_map = {
        0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'
    }
    
    has_roster_this_month = len(roster_map) > 0
    has_regular_day = len(regular_map) > 0
    has_dept_day = len(dept_map) > 0
    
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
            "jam_absen_pulang": None,
            "status": None
        }
        
        # Logic Priority: Extra Date -> Roster Date -> Regular Day -> Dept Day -> Default
        final_kode = None
        is_roster = False
        
        if curr in extra_date_map:
            final_kode = extra_date_map[curr]
            is_roster = True
        elif curr in roster_map:
            final_kode = roster_map[curr]
            is_roster = True
        elif has_roster_this_month:
            # If they have a roster this month, and this day is NOT in the roster, it's a day off.
            final_kode = None
            is_roster = False
        elif day_name in regular_map:
            final_kode = regular_map[day_name]
            is_roster = False
        elif has_regular_day:
            # If they have a regular day config, and this day is NOT in it (like Saturday/Sunday), it's a day off.
            final_kode = None
            is_roster = False
        elif day_name in dept_map:
            final_kode = dept_map[day_name]
            is_roster = False
        elif has_dept_day:
            final_kode = None
            is_roster = False
        else:
            final_kode = karyawan.kode_jadwal
            is_roster = False
            
        jk_obj = jk_map.get(final_kode) if final_kode else None
            
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
            item["status"] = p.status if p.status else "H"
        else:
            if curr in izin_map:
                item["status"] = izin_map[curr]
                
        jadwal_full.append(item)
        curr += timedelta(days=1)

    return {
        "status": True,
        "message": "Jadwal bulanan berhasil diambil",
        "data": jadwal_full
    }
