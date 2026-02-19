from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_, or_
from app.database import get_db
from app.models.models import Presensi, Karyawan, Cabang, Departemen, PresensiJamkerja, PresensiIzin, PresensiIzindinas, PresensiIzinsakit, PresensiIzincuti, SetJamKerjaByDay, SetJamKerjaByDate, Jabatan
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from datetime import date, datetime, timedelta, time
from app.core.permissions import CurrentUser, require_permission_dependency
import math

router = APIRouter(
    prefix="/api/laporan",
    tags=["Laporan"]
)

class LaporanPresensiDTO(BaseModel):
    nik: str
    nama_karyawan: str
    nama_dept: Optional[str]
    nama_cabang: Optional[str]
    nama_jabatan: Optional[str]
    tanggal: date
    kode_jam_kerja: Optional[str]
    nama_jam_kerja: Optional[str]
    jam_masuk_jadwal: Optional[str]
    jam_pulang_jadwal: Optional[str]
    jam_in: Optional[str]
    jam_out: Optional[str]
    status: str
    keterangan: Optional[str]
    foto_in: Optional[str]
    foto_out: Optional[str]
    lokasi_in: Optional[str]
    lokasi_out: Optional[str]
    terlambat: Optional[str]
    pulang_cepat: Optional[str]
    denda: Optional[float] = 0
    potongan_jam: Optional[float] = 0
    lembur: Optional[float] = 0
    total_jam: Optional[float] = 0
    
    class Config:
        from_attributes = True

class LaporanPresensiResponse(BaseModel):
    status: bool
    data: List[LaporanPresensiDTO]

class RekapPresensiDTO(BaseModel):
    nik: str
    nama_karyawan: str
    nama_dept: str
    nama_cabang: str
    nama_jabatan: Optional[str]
    data_tanggal: Dict[str, Any] # Key is date string YYYY-MM-DD
    summary: Dict[str, Any] # hadir, sakit, izin, alpha, libur, terlambat, denda, potongan, lembur

class RekapPresensiResponse(BaseModel):
    status: bool
    data: List[RekapPresensiDTO]
    dates: List[str]

# ==========================================
# HELPERS
# ==========================================

def calculate_time_diff_hours(start_time: datetime, end_time: datetime) -> float:
    diff = end_time - start_time
    return diff.total_seconds() / 3600

def get_jam_kerja_karyawan(db: Session, nik: str, tanggal: date):
    # Check by Date
    by_date = db.query(SetJamKerjaByDate).filter(
        SetJamKerjaByDate.nik == nik, 
        SetJamKerjaByDate.tanggal == tanggal
    ).first()
    
    if by_date and by_date.jam_kerja:
        return by_date.jam_kerja
        
    # Check by Day
    hari_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    hari_str = hari_map[tanggal.weekday()]
    
    by_day = db.query(SetJamKerjaByDay).filter(
        SetJamKerjaByDay.nik == nik, 
        SetJamKerjaByDay.hari == hari_str
    ).first()
    
    if by_day and by_day.jam_kerja:
        return by_day.jam_kerja
        
    return None

def hitung_terlambat(jam_in: datetime, jam_masuk: time, tanggal: date) -> dict:
    # Construct datetime for jam_masuk
    jam_masuk_dt = datetime.combine(tanggal, jam_masuk)
    
    # If jam_in is None or earlier, not late
    if not jam_in:
        return {"telat": False, "menit": 0, "jam": 0}
        
    if jam_in <= jam_masuk_dt:
        return {"telat": False, "menit": 0, "jam": 0}
        
    diff = jam_in - jam_masuk_dt
    menit = diff.total_seconds() / 60
    jam = diff.total_seconds() / 3600
    
    return {"telat": True, "menit": int(menit), "jam": round(jam, 2)}

def hitung_pulang_cepat(jam_out: datetime, jam_pulang: time, tanggal: date, lintas_hari: bool = False) -> float:
    if not jam_out:
        return 0
        
    # Construct datetime for jam_pulang
    jam_pulang_dt = datetime.combine(tanggal, jam_pulang)
    
    if lintas_hari:
         jam_pulang_dt += timedelta(days=1)
    
    if jam_out >= jam_pulang_dt:
        return 0
        
    diff = jam_pulang_dt - jam_out
    jam = diff.total_seconds() / 3600
    return round(jam, 2)

# ==========================================
# ENDPOINTS
# ==========================================

@router.get("/presensi", response_model=LaporanPresensiResponse)
async def get_laporan_presensi(
    start_date: date,
    end_date: date,
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    # current_user: CurrentUser = Depends(require_permission_dependency("laporan.presensi")),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(
            Presensi, 
            Karyawan, 
            Cabang.nama_cabang, 
            Departemen.nama_dept,
            PresensiJamkerja,
            Jabatan.nama_jabatan
        ).join(Karyawan, Presensi.nik == Karyawan.nik)\
         .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
         .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
         .outerjoin(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
         .outerjoin(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
         .filter(Presensi.tanggal >= start_date, Presensi.tanggal <= end_date)
        
        if kode_cabang:
            query = query.filter(Karyawan.kode_cabang == kode_cabang)
            
        if kode_dept:
            query = query.filter(Karyawan.kode_dept == kode_dept)
            
        if search:
            query = query.filter(
                or_(
                    Karyawan.nama_karyawan.like(f"%{search}%"),
                    Karyawan.nik.like(f"%{search}%")
                )
            )
            
        results = query.order_by(Presensi.tanggal.desc(), Karyawan.nama_karyawan).all()
        
        data_list = []
        for row in results:
            presensi = row[0]
            karyawan = row[1]
            nama_cabang = row[2]
            nama_dept = row[3]
            jam_kerja = row[4]
            nama_jabatan = row[5]
            
            # Helper Formatters
            def fmt_time(dt):
                return dt.strftime("%H:%M:%S") if dt else "-"
            
            # Determine Schedule
            jam_masuk = jam_kerja.jam_masuk if jam_kerja else None
            jam_pulang = jam_kerja.jam_pulang if jam_kerja else None
            
            # Calc Logic
            terlambat = "-"
            pulang_cepat = "-"
            denda = 0
            potongan_jam = 0
            total_jam = 0
            
            if presensi.jam_in and jam_masuk:
                res_telat = hitung_terlambat(presensi.jam_in, jam_masuk, presensi.tanggal)
                if res_telat['telat']:
                    # Format: XX Jam XX Menit or just time diff
                    import math
                    h = math.floor(res_telat['menit'] / 60)
                    m = res_telat['menit'] % 60
                    terlambat = f"{h} Jam {m} Menit" if h > 0 else f"{m} Menit"
                    # Need Denda Logic here if tables exist
            
            if presensi.jam_out and jam_pulang:
               res_pc = hitung_pulang_cepat(presensi.jam_out, jam_pulang, presensi.tanggal, presensi.lintashari)
               if res_pc > 0:
                   pulang_cepat = f"{res_pc} Jam"
                   potongan_jam += res_pc # Naive logic from blade
                   
            if presensi.jam_in and presensi.jam_out:
                diff_seconds = (presensi.jam_out - presensi.jam_in).total_seconds()
                total_jam = round(diff_seconds / 3600, 2)

            data_list.append(LaporanPresensiDTO(
                nik=karyawan.nik,
                nama_karyawan=karyawan.nama_karyawan,
                nama_dept=nama_dept,
                nama_cabang=nama_cabang,
                nama_jabatan=nama_jabatan,
                tanggal=presensi.tanggal,
                kode_jam_kerja=presensi.kode_jam_kerja,
                nama_jam_kerja=jam_kerja.nama_jam_kerja if jam_kerja else None,
                jam_masuk_jadwal=fmt_time(jam_masuk),
                jam_pulang_jadwal=fmt_time(jam_pulang),
                jam_in=fmt_time(presensi.jam_in),
                jam_out=fmt_time(presensi.jam_out),
                status=presensi.status,
                keterangan=None, 
                foto_in=presensi.foto_in,
                foto_out=presensi.foto_out,
                lokasi_in=presensi.lokasi_in,
                lokasi_out=presensi.lokasi_out,
                terlambat=terlambat,
                pulang_cepat=pulang_cepat,
                denda=denda,
                potongan_jam=potongan_jam,
                total_jam=total_jam
            ))
            
        return {"status": True, "data": data_list}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rekap-presensi", response_model=RekapPresensiResponse)
async def get_rekap_presensi(
    start_date: date,
    end_date: date,
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        # 1. Fetch Employees
        # 1. Fetch Employees
        query_karyawan = db.query(Karyawan, Cabang, Departemen, Jabatan)\
            .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
            .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
            .outerjoin(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)
            
        if kode_cabang:
            query_karyawan = query_karyawan.filter(Karyawan.kode_cabang == kode_cabang)
        if kode_dept:
            query_karyawan = query_karyawan.filter(Karyawan.kode_dept == kode_dept)
        if search:
            query_karyawan = query_karyawan.filter(
                or_(
                    Karyawan.nama_karyawan.like(f"%{search}%"),
                    Karyawan.nik.like(f"%{search}%")
                )
            )
            
        karyawans = query_karyawan.order_by(Karyawan.nama_karyawan).all()
        
        # 2. Fetch Presensi in Range
        presensi_records = db.query(Presensi, PresensiJamkerja)\
            .outerjoin(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .filter(Presensi.tanggal >= start_date, Presensi.tanggal <= end_date)\
            .all()
            
        # Organize Presensi by NIK -> Date
        presensi_map = {} # {nik: {date_str: record}}
        for p, jk in presensi_records:
            if p.nik not in presensi_map:
                presensi_map[p.nik] = {}
            presensi_map[p.nik][str(p.tanggal)] = {
                "status": p.status,
                "jam_in": p.jam_in,
                "jam_out": p.jam_out,
                "jam_masuk": jk.jam_masuk if jk else None,
                "jam_pulang": jk.jam_pulang if jk else None,
                "lintashari": p.lintashari
            }

        # 3. Generate Date List
        dates = []
        curr = start_date
        while curr <= end_date:
            dates.append(str(curr))
            curr += timedelta(days=1)
            
        # 4. Build Response
        rekap_list = []
        for row in karyawans:
            k = row[0]
            c = row[1]
            d = row[2]
            j = row[3]
            
            data_tanggal = {}
            summary = {
                "hadir": 0, "sakit": 0, "izin": 0, "alpha": 0, "cuti": 0, 
                "terlambat": 0, "tidak_scan_masuk": 0, "tidak_scan_pulang": 0
            }
            
            employee_presensi = presensi_map.get(k.nik, {})
            
            for d_str in dates:
                record = employee_presensi.get(d_str)
                d_date = datetime.strptime(d_str, "%Y-%m-%d").date()
                
                cell_data = {
                    "status": "a", # Default Alpha
                    "ket": "-"
                }
                
                if record:
                    cell_data["status"] = record["status"]
                    status = record["status"]
                    
                    if status == 'h':
                        summary["hadir"] += 1
                        
                        # Late Check
                        if record["jam_in"] and record["jam_masuk"]:
                             res_telat = hitung_terlambat(record["jam_in"], record["jam_masuk"], d_date)
                             if res_telat["telat"]:
                                 summary["terlambat"] += 1
                                 
                        if not record["jam_in"]: summary["tidak_scan_masuk"] += 1
                        if not record["jam_out"]: summary["tidak_scan_pulang"] += 1
                        
                    elif status == 's': summary["sakit"] += 1
                    elif status == 'i': summary["izin"] += 1
                    elif status == 'c': summary["cuti"] += 1
                    elif status == 'a': summary["alpha"] += 1
                    
                else:
                    # No record -> Check Calendar/Holiday/Schedule?
                    # For now assume Alpha
                    summary["alpha"] += 1
                
                data_tanggal[d_str] = cell_data

            rekap_list.append(RekapPresensiDTO(
                nik=k.nik,
                nama_karyawan=k.nama_karyawan,
                nama_dept=d.nama_dept if d else "-",
                nama_cabang=c.nama_cabang if c else "-",
                nama_jabatan=j.nama_jabatan if j else "-",
                data_tanggal=data_tanggal,
                summary=summary
            ))
            
        return {"status": True, "data": rekap_list, "dates": dates}
        
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))
