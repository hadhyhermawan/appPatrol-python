from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_, or_
from app.database import get_db
from app.models.models import Presensi, Karyawan, Cabang, Departemen, PresensiJamkerja, PresensiIzin, PresensiIzindinas, PresensiIzinsakit, PresensiIzincuti, SetJamKerjaByDay, SetJamKerjaByDate, Jabatan, KaryawanGajiPokok, KaryawanTunjangan, KaryawanTunjanganDetail, KaryawanBpjsKesehatan, KaryawanBpjstenagakerja, KaryawanPenyesuaianGaji, KaryawanPenyesuaianGajiDetail, JenisTunjangan
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

class LaporanGajiDTO(BaseModel):
    nik: str
    nama_karyawan: str
    nama_dept: str
    nama_cabang: str
    nama_jabatan: str
    gaji_pokok: float
    bpjs_kesehatan: float
    bpjs_tenagakerja: float
    penambah: float
    pengurang: float
    gaji_bersih: float
    tunjangan_detail: Dict[str, float]

class LaporanGajiResponse(BaseModel):
    status: bool
    data: List[LaporanGajiDTO]
    jenis_tunjangan: List[Dict[str, str]]

class LaporanPerformanceDTO(BaseModel):
    nik: str
    nama_karyawan: str
    nama_dept: str
    nama_cabang: str
    hadir: int
    tugas_patroli: int
    safety_briefing: int
    tamu: int
    barang: int
    turlalin: int
    surat: int
    pelanggaran: int

class LaporanPerformanceResponse(BaseModel):
    status: bool
    data: List[LaporanPerformanceDTO]

# ==========================================
# HELPERS
# ==========================================

def calculate_time_diff_hours(start_time: datetime, end_time: datetime) -> float:
    diff = end_time - start_time
    return diff.total_seconds() / 3600

def build_schedule_map(db: Session, karyawans: list, dates: list) -> dict:
    from app.models.models import PresensiJamkerjaBydateExtra, SetJamKerjaByDate, SetJamKerjaByDay, PresensiJamkerjaBydept, PresensiJamkerjaBydeptDetail
    from sqlalchemy import extract
    
    if not karyawans or not dates: return {}
    
    nik_list = [k.nik for k in karyawans if hasattr(k, 'nik')]
    if not nik_list:
        try:
             # handle tuple cases (Karyawan, Cabang, Departemen, Jabatan)
             nik_list = [row[0].nik for row in karyawans]
        except:
             pass
             
    start_date = min(dates)
    end_date = max(dates)
    
    # 1. Extra Date
    extra_dates = db.query(PresensiJamkerjaBydateExtra)\
        .filter(PresensiJamkerjaBydateExtra.tanggal >= start_date, PresensiJamkerjaBydateExtra.tanggal <= end_date, PresensiJamkerjaBydateExtra.nik.in_(nik_list)).all()
    extra_date_map = {(e.nik, e.tanggal): e.kode_jam_kerja for e in extra_dates}
    
    # 2. Roster
    roster_date_map = {}
    roster_months_map = {}
    unique_months = set((d.year, d.month) for d in dates)
    for y, m in unique_months:
        rosters = db.query(SetJamKerjaByDate).filter(
            extract('year', SetJamKerjaByDate.tanggal) == y,
            extract('month', SetJamKerjaByDate.tanggal) == m,
            SetJamKerjaByDate.nik.in_(nik_list)
        ).all()
        for r in rosters:
            roster_months_map[(r.nik, y, m)] = True
            if start_date <= r.tanggal <= end_date:
                roster_date_map[(r.nik, r.tanggal)] = r.kode_jam_kerja
                
    # 3. Regular
    regular_days = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik.in_(nik_list)).all()
    regular_day_map = {}
    has_regular_day_map = {}
    for r in regular_days:
        has_regular_day_map[r.nik] = True
        regular_day_map[(r.nik, r.hari)] = r.kode_jam_kerja
        
    # 4. Dept
    dept_headers = db.query(PresensiJamkerjaBydept).all()
    dept_header_map = {(d.kode_dept, d.kode_cabang): d.kode_jk_dept for d in dept_headers}
    dept_details = db.query(PresensiJamkerjaBydeptDetail).all()
    dept_detail_map = {}
    has_dept_day_map = {}
    for d in dept_details:
        has_dept_day_map[d.kode_jk_dept] = True
        dept_detail_map[(d.kode_jk_dept, d.hari)] = d.kode_jam_kerja
        
    days_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    
    schedule_map = {}
    for row in karyawans:
        if hasattr(row, 'nik'):
            k = row
        else:
            k = row[0]
            
        nik = k.nik
        kode_dept = getattr(k, 'kode_dept', None)
        kode_cabang = getattr(k, 'kode_cabang', None)
        kode_jadwal = getattr(k, 'kode_jadwal', None)
        
        kode_jk_dept = dept_header_map.get((kode_dept, kode_cabang))
        has_dept_day = has_dept_day_map.get(kode_jk_dept, False) if kode_jk_dept else False
        has_regular_day = has_regular_day_map.get(nik, False)
        
        for d in dates:
            day_name = days_map[d.weekday()]
            y, m = d.year, d.month
            has_roster_this_month = roster_months_map.get((nik, y, m), False)
            
            final_kode = None
            if (nik, d) in extra_date_map:
                final_kode = extra_date_map[(nik, d)]
            elif (nik, d) in roster_date_map:
                final_kode = roster_date_map[(nik, d)]
            elif has_roster_this_month:
                final_kode = None
            elif (nik, day_name) in regular_day_map:
                final_kode = regular_day_map[(nik, day_name)]
            elif has_regular_day:
                final_kode = None
            elif kode_jk_dept and (kode_jk_dept, day_name) in dept_detail_map:
                final_kode = dept_detail_map[(kode_jk_dept, day_name)]
            elif has_dept_day:
                final_kode = None
            else:
                final_kode = kode_jadwal
                
            schedule_map[(nik, d)] = final_kode
            
    return schedule_map

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
        # 1. Generate dates
        dates = []
        curr = start_date
        while curr <= end_date:
            dates.append(curr)
            curr += timedelta(days=1)
            
        # 2. Fetch Karyawan
        query_karyawan = db.query(Karyawan, Cabang, Departemen, Jabatan)\
            .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
            .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
            .outerjoin(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
            .filter(Karyawan.status_aktif_karyawan == '1')
            
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
        karyawans = query_karyawan.all()
        
        # 3. Fetch Presensi
        presensi_records = db.query(Presensi, PresensiJamkerja)\
            .outerjoin(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .filter(Presensi.tanggal >= start_date, Presensi.tanggal <= end_date)\
            .all()
            
        presensi_map = {}
        for p, jk in presensi_records:
            if p.nik not in presensi_map:
                presensi_map[p.nik] = {}
            if p.tanggal not in presensi_map[p.nik]:
                presensi_map[p.nik][p.tanggal] = []
            presensi_map[p.nik][p.tanggal].append((p, jk))

        # 3.5 Fetch Izin
        from app.models.models import PresensiIzinabsen, PresensiIzindinas, PresensiIzinsakit, PresensiIzincuti
        izin_map = {}
        
        def populate_izin(records, status_code):
            for r in records:
                if str(r.status) != '1': continue
                curr_izin = r.dari
                while curr_izin <= r.sampai:
                    if r.nik not in izin_map: izin_map[r.nik] = {}
                    izin_map[r.nik][curr_izin] = status_code
                    curr_izin += timedelta(days=1)
                    
        izin_absens = db.query(PresensiIzinabsen).filter(and_(PresensiIzinabsen.dari <= end_date, PresensiIzinabsen.sampai >= start_date)).all()
        populate_izin(izin_absens, 'I')
        
        izin_sakits = db.query(PresensiIzinsakit).filter(and_(PresensiIzinsakit.dari <= end_date, PresensiIzinsakit.sampai >= start_date)).all()
        populate_izin(izin_sakits, 'S')
        
        izin_cutis = db.query(PresensiIzincuti).filter(and_(PresensiIzincuti.dari <= end_date, PresensiIzincuti.sampai >= start_date)).all()
        populate_izin(izin_cutis, 'C')
        
        izin_dinas = db.query(PresensiIzindinas).filter(and_(PresensiIzindinas.dari <= end_date, PresensiIzindinas.sampai >= start_date)).all()
        populate_izin(izin_dinas, 'DL')
        
        schedule_map = build_schedule_map(db, karyawans, dates)
        
        # Helper Cache for JamKerja details
        all_jks = db.query(PresensiJamkerja).all()
        jk_detail_map = {jk.kode_jam_kerja: jk for jk in all_jks}

        data_list = []
        for row in karyawans:
            karyawan = row[0]
            cabang = row[1]
            dept = row[2]
            jabatan = row[3]
            
            for d in dates:
                emp_records = presensi_map.get(karyawan.nik, {}).get(d, [])
                predicted_jk_kode = schedule_map.get((karyawan.nik, d))
                predicted_jk = jk_detail_map.get(predicted_jk_kode) if predicted_jk_kode else None
                
                if not emp_records:
                    default_status = izin_map.get(karyawan.nik, {}).get(d, "A")
                    if default_status == "A" and predicted_jk_kode is None:
                        default_status = "LIBR" # Libur
                        
                    data_list.append(LaporanPresensiDTO(
                        nik=karyawan.nik,
                        nama_karyawan=karyawan.nama_karyawan,
                        nama_dept=dept.nama_dept if dept else "-",
                        nama_cabang=cabang.nama_cabang if cabang else "-",
                        nama_jabatan=jabatan.nama_jabatan if jabatan else "-",
                        tanggal=d,
                        kode_jam_kerja=predicted_jk_kode,
                        nama_jam_kerja=predicted_jk.nama_jam_kerja if predicted_jk else None,
                        jam_masuk_jadwal=predicted_jk.jam_masuk.strftime("%H:%M:%S") if predicted_jk and predicted_jk.jam_masuk else "-",
                        jam_pulang_jadwal=predicted_jk.jam_pulang.strftime("%H:%M:%S") if predicted_jk and predicted_jk.jam_pulang else "-",
                        jam_in="-",
                        jam_out="-",
                        status=default_status,
                        keterangan=None,
                        foto_in=None,
                        foto_out=None,
                        lokasi_in=None,
                        lokasi_out=None,
                        terlambat="-",
                        pulang_cepat="-",
                        denda=0,
                        potongan_jam=0,
                        total_jam=0
                    ))
                else:
                    for presensi, jam_kerja in emp_records:
                        def fmt_time(dt):
                            return dt.strftime("%H:%M:%S") if dt else "-"
                        
                        jam_masuk = jam_kerja.jam_masuk if jam_kerja else None
                        jam_pulang = jam_kerja.jam_pulang if jam_kerja else None
                        
                        terlambat = "-"
                        pulang_cepat = "-"
                        denda = 0
                        potongan_jam = 0
                        total_jam = 0
                        
                        if presensi.jam_in and jam_masuk:
                            res_telat = hitung_terlambat(presensi.jam_in, jam_masuk, presensi.tanggal)
                            if res_telat['telat']:
                                import math
                                h = math.floor(res_telat['menit'] / 60)
                                m = int(res_telat['menit'] % 60)
                                terlambat = f"{h} Jam {m} Menit" if h > 0 else f"{m} Menit"
                        
                        if presensi.jam_out and jam_pulang:
                            res_pc = hitung_pulang_cepat(presensi.jam_out, jam_pulang, presensi.tanggal, presensi.lintashari)
                            if res_pc > 0:
                                pulang_cepat = f"{res_pc} Jam"
                                potongan_jam += res_pc
                        
                        if presensi.jam_in and presensi.jam_out:
                            diff_seconds = (presensi.jam_out - presensi.jam_in).total_seconds()
                            total_jam = round(diff_seconds / 3600, 2)
                            
                        data_list.append(LaporanPresensiDTO(
                            nik=karyawan.nik,
                            nama_karyawan=karyawan.nama_karyawan,
                            nama_dept=dept.nama_dept if dept else "-",
                            nama_cabang=cabang.nama_cabang if cabang else "-",
                            nama_jabatan=jabatan.nama_jabatan if jabatan else "-",
                            tanggal=presensi.tanggal,
                            kode_jam_kerja=presensi.kode_jam_kerja,
                            nama_jam_kerja=jam_kerja.nama_jam_kerja if jam_kerja else None,
                            jam_masuk_jadwal=fmt_time(jam_masuk),
                            jam_pulang_jadwal=fmt_time(jam_pulang),
                            jam_in=fmt_time(presensi.jam_in),
                            jam_out=fmt_time(presensi.jam_out),
                            status=str(presensi.status).upper() if presensi.status else "H",
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
        
        data_list.sort(key=lambda x: (-x.tanggal.toordinal(), x.nama_karyawan))
        return {"status": True, "data": data_list}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
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
            
        # 3.5 Fetch Izin
        from app.models.models import PresensiIzinabsen, PresensiIzindinas, PresensiIzinsakit, PresensiIzincuti
        izin_map = {}
        
        def populate_izin(records, status_code):
            for r in records:
                if str(r.status) != '1': continue
                curr_izin = r.dari
                while curr_izin <= r.sampai:
                    if r.nik not in izin_map: izin_map[r.nik] = {}
                    izin_map[r.nik][str(curr_izin)] = status_code
                    curr_izin += timedelta(days=1)
                    
        izin_absens = db.query(PresensiIzinabsen).filter(and_(PresensiIzinabsen.dari <= end_date, PresensiIzinabsen.sampai >= start_date)).all()
        populate_izin(izin_absens, 'I')
        
        izin_sakits = db.query(PresensiIzinsakit).filter(and_(PresensiIzinsakit.dari <= end_date, PresensiIzinsakit.sampai >= start_date)).all()
        populate_izin(izin_sakits, 'S')
        
        izin_cutis = db.query(PresensiIzincuti).filter(and_(PresensiIzincuti.dari <= end_date, PresensiIzincuti.sampai >= start_date)).all()
        populate_izin(izin_cutis, 'C')
        
        izin_dinas = db.query(PresensiIzindinas).filter(and_(PresensiIzindinas.dari <= end_date, PresensiIzindinas.sampai >= start_date)).all()
        populate_izin(izin_dinas, 'DL')
        
        # 3.8 Fetch Schedules to detect holidays
        d_objects = [datetime.strptime(d, "%Y-%m-%d").date() for d in dates]
        schedule_map = build_schedule_map(db, karyawans, d_objects)

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
                "terlambat": 0, "tidak_scan_masuk": 0, "tidak_scan_pulang": 0, "ta": 0, "dl": 0, "libur": 0
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
                    raw_status = record["status"].lower() if record.get("status") else "-"
                    cell_data["status"] = raw_status
                    
                    if raw_status == 'h':
                        summary["hadir"] += 1
                        
                        # Late Check
                        if record["jam_in"] and record["jam_masuk"]:
                             res_telat = hitung_terlambat(record["jam_in"], record["jam_masuk"], d_date)
                             if res_telat["telat"]:
                                 summary["terlambat"] += 1
                                 
                        if not record["jam_in"]: summary["tidak_scan_masuk"] += 1
                        if not record["jam_out"]: summary["tidak_scan_pulang"] += 1
                        
                    elif raw_status == 's': summary["sakit"] += 1
                    elif raw_status == 'i': summary["izin"] += 1
                    elif raw_status == 'c': summary["cuti"] += 1
                    elif raw_status == 'a': summary["alpha"] += 1
                    elif raw_status in ['ta', 'dl', 'lb', 'libr']: 
                        # Count TA as TA specifically for frontend
                        if raw_status == 'ta':
                            summary["ta"] += 1
                        elif raw_status == 'dl':
                            summary["dl"] += 1
                        elif raw_status in ['lb', 'libr']:
                            summary["libur"] += 1
                    
                else:
                    # No record -> Check Izin then Schedule then Alpha
                    predicted_jk = schedule_map.get((k.nik, d_date))
                    izin_status = izin_map.get(k.nik, {}).get(d_str, "a")
                    
                    if izin_status == "a" and predicted_jk is None:
                        izin_status = "libr"
                        
                    cell_data["status"] = izin_status
                    raw_status = izin_status.lower()
                    if raw_status == 'a': summary["alpha"] += 1
                    elif raw_status == 's': summary["sakit"] += 1
                    elif raw_status == 'i': summary["izin"] += 1
                    elif raw_status == 'c': summary["cuti"] += 1
                    elif raw_status == 'dl': summary["dl"] += 1
                    elif raw_status == 'libr': summary["libur"] += 1
                
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gaji", response_model=LaporanGajiResponse)
async def get_laporan_gaji(
    bulan: int = Query(..., description="Bulan (1-12)"),
    tahun: int = Query(..., description="Tahun (YYYY)"),
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        import calendar
        last_day = calendar.monthrange(tahun, bulan)[1]
        periode_sampai = date(tahun, bulan, last_day)

        # 1. Fetch Jenis Tunjangan for dynamic columns
        jenis_tunjangan_all = db.query(JenisTunjangan).order_by(JenisTunjangan.kode_jenis_tunjangan).all()
        tunjangan_columns = [{"kode": jt.kode_jenis_tunjangan, "nama": jt.jenis_tunjangan} for jt in jenis_tunjangan_all]

        # 2. Fetch Employees
        query_karyawan = db.query(Karyawan, Cabang, Departemen, Jabatan)\
            .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
            .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
            .outerjoin(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
            .filter(Karyawan.status_aktif_karyawan == '1')
            
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

        laporan_list = []
        for row in karyawans:
            emp = row[0]
            c = row[1]
            d = row[2]
            j = row[3]

            # 3. Get Gaji Pokok (Latest valid)
            gaji_pokok_item = db.query(KaryawanGajiPokok)\
                .filter(KaryawanGajiPokok.nik == emp.nik)\
                .filter(KaryawanGajiPokok.tanggal_berlaku <= periode_sampai)\
                .order_by(KaryawanGajiPokok.tanggal_berlaku.desc())\
                .first()
            gaji_pokok = float(gaji_pokok_item.jumlah) if gaji_pokok_item else 0.0

            # 4. Get Tunjangan
            tunjangan_header = db.query(KaryawanTunjangan)\
                .filter(KaryawanTunjangan.nik == emp.nik)\
                .filter(KaryawanTunjangan.tanggal_berlaku <= periode_sampai)\
                .order_by(KaryawanTunjangan.tanggal_berlaku.desc())\
                .first()
            
            tunjangan_detail_dict = {col["kode"]: 0.0 for col in tunjangan_columns}
            if tunjangan_header:
                details = db.query(KaryawanTunjanganDetail)\
                    .filter(KaryawanTunjanganDetail.kode_tunjangan == tunjangan_header.kode_tunjangan)\
                    .all()
                for d_item in details:
                     if d_item.kode_jenis_tunjangan in tunjangan_detail_dict:
                         tunjangan_detail_dict[d_item.kode_jenis_tunjangan] = float(d_item.jumlah)

            # 5. Get BPJS
            bpjs_kes_item = db.query(KaryawanBpjsKesehatan)\
                .filter(KaryawanBpjsKesehatan.nik == emp.nik)\
                .filter(KaryawanBpjsKesehatan.tanggal_berlaku <= periode_sampai)\
                .order_by(KaryawanBpjsKesehatan.tanggal_berlaku.desc())\
                .first()
            bpjs_kes = float(bpjs_kes_item.jumlah) if bpjs_kes_item else 0.0
            
            bpjs_tk_item = db.query(KaryawanBpjstenagakerja)\
                .filter(KaryawanBpjstenagakerja.nik == emp.nik)\
                .filter(KaryawanBpjstenagakerja.tanggal_berlaku <= periode_sampai)\
                .order_by(KaryawanBpjstenagakerja.tanggal_berlaku.desc())\
                .first()
            bpjs_tk = float(bpjs_tk_item.jumlah) if bpjs_tk_item else 0.0

            # 6. Get Penyesuaian Gaji for this period
            bulan_str = str(bulan).zfill(2)
            kode_pyg = f"PYG{bulan_str}{tahun}"
            
            penyesuaian_item = db.query(KaryawanPenyesuaianGajiDetail)\
                .filter(KaryawanPenyesuaianGajiDetail.kode_penyesuaian_gaji == kode_pyg)\
                .filter(KaryawanPenyesuaianGajiDetail.nik == emp.nik)\
                .first()
            
            penambah = float(penyesuaian_item.penambah) if penyesuaian_item else 0.0
            pengurang = float(penyesuaian_item.pengurang) if penyesuaian_item else 0.0

            # Calculate total
            total_tunjangan_value = sum(tunjangan_detail_dict.values())
            total_penerimaan = gaji_pokok + total_tunjangan_value + penambah
            total_potongan = bpjs_kes + bpjs_tk + pengurang
            gaji_bersih = total_penerimaan - total_potongan

            laporan_list.append(LaporanGajiDTO(
                nik=emp.nik,
                nama_karyawan=emp.nama_karyawan,
                nama_dept=d.nama_dept if d else "-",
                nama_cabang=c.nama_cabang if c else "-",
                nama_jabatan=j.nama_jabatan if j else "-",
                gaji_pokok=gaji_pokok,
                bpjs_kesehatan=bpjs_kes,
                bpjs_tenagakerja=bpjs_tk,
                penambah=penambah,
                pengurang=pengurang,
                gaji_bersih=gaji_bersih,
                tunjangan_detail=tunjangan_detail_dict
            ))
            
        return {"status": True, "data": laporan_list, "jenis_tunjangan": tunjangan_columns}
        
    except Exception as e:
         import traceback
         traceback.print_exc()
         raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance", response_model=LaporanPerformanceResponse)
async def get_laporan_performance(
    start_date: date,
    end_date: date,
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        from app.models.models import (
            PatrolSessions, SafetyBriefings, Tamu, BarangMasuk, 
            Turlalin, SuratMasuk, Violation
        )
        
        query_karyawan = db.query(Karyawan, Cabang, Departemen)\
            .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
            .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
            .filter(Karyawan.status_aktif_karyawan == '1')
            
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
        nik_list = [k.nik for k, c, d in karyawans]
        
        if not nik_list:
            return {"status": True, "data": []}

        presensi_counts = dict(db.query(Presensi.nik, func.count(Presensi.id))\
            .filter(Presensi.tanggal >= start_date, Presensi.tanggal <= end_date, Presensi.status.in_(['H', 'h', 'HADIR', 'hadir']))\
            .filter(Presensi.nik.in_(nik_list)).group_by(Presensi.nik).all())
            
        patrol_counts = dict(db.query(PatrolSessions.nik, func.count(PatrolSessions.id))\
            .filter(func.date(PatrolSessions.tanggal) >= start_date, func.date(PatrolSessions.tanggal) <= end_date)\
            .filter(PatrolSessions.nik.in_(nik_list)).group_by(PatrolSessions.nik).all())
            
        safety_counts = dict(db.query(SafetyBriefings.nik, func.count(SafetyBriefings.id))\
            .filter(func.date(SafetyBriefings.tanggal_jam) >= start_date, func.date(SafetyBriefings.tanggal_jam) <= end_date)\
            .filter(SafetyBriefings.nik.in_(nik_list)).group_by(SafetyBriefings.nik).all())
            
        tamu_counts = dict(db.query(Tamu.nik_satpam, func.count(Tamu.id_tamu))\
            .filter(func.date(Tamu.jam_masuk) >= start_date, func.date(Tamu.jam_masuk) <= end_date)\
            .filter(Tamu.nik_satpam.in_(nik_list)).group_by(Tamu.nik_satpam).all())
            
        barang_counts = dict(db.query(BarangMasuk.nik_satpam, func.count(BarangMasuk.id_barang_masuk))\
            .filter(func.date(BarangMasuk.tgl_jam_masuk) >= start_date, func.date(BarangMasuk.tgl_jam_masuk) <= end_date)\
            .filter(BarangMasuk.nik_satpam.in_(nik_list)).group_by(BarangMasuk.nik_satpam).all())
            
        turlalin_counts = dict(db.query(Turlalin.nik, func.count(Turlalin.id))\
            .filter(func.date(Turlalin.jam_masuk) >= start_date, func.date(Turlalin.jam_masuk) <= end_date)\
            .filter(Turlalin.nik.in_(nik_list)).group_by(Turlalin.nik).all())
            
        surat_counts = dict(db.query(SuratMasuk.nik_satpam, func.count(SuratMasuk.id))\
            .filter(func.date(SuratMasuk.tanggal_surat) >= start_date, func.date(SuratMasuk.tanggal_surat) <= end_date)\
            .filter(SuratMasuk.nik_satpam.in_(nik_list)).group_by(SuratMasuk.nik_satpam).all())
            
        violation_counts = dict(db.query(Violation.nik, func.count(Violation.id))\
            .filter(Violation.tanggal_pelanggaran >= start_date, Violation.tanggal_pelanggaran <= end_date)\
            .filter(Violation.nik.in_(nik_list)).group_by(Violation.nik).all())

        laporan_list = []
        for emp, c, d in karyawans:
            nik = emp.nik
            laporan_list.append(LaporanPerformanceDTO(
                nik=nik,
                nama_karyawan=emp.nama_karyawan,
                nama_dept=d.nama_dept if d else "-",
                nama_cabang=c.nama_cabang if c else "-",
                hadir=presensi_counts.get(nik, 0),
                tugas_patroli=patrol_counts.get(nik, 0),
                safety_briefing=safety_counts.get(nik, 0),
                tamu=tamu_counts.get(nik, 0),
                barang=barang_counts.get(nik, 0),
                turlalin=turlalin_counts.get(nik, 0),
                surat=surat_counts.get(nik, 0),
                pelanggaran=violation_counts.get(nik, 0),
            ))
            
        return {"status": True, "data": laporan_list}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
