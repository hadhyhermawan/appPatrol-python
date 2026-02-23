from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.database import get_db
from app.models.models import (
    Karyawan, PatrolSessions, PatrolSchedules, PresensiJamkerja, Cabang,
    SetJamKerjaByDate, SetJamKerjaByDay, PresensiJamkerjaBydept,
    PresensiJamkerjaBydeptDetail, PresensiJamkerjaBydateExtra
)
from datetime import date, datetime, timedelta, time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import calendar
from app.core.permissions import require_permission_dependency

router = APIRouter(prefix="/api/monitoring-regu", tags=["Monitoring Regu Legacy"])

# --- Models ---

class ReguMember(BaseModel):
    nik: str
    nama_karyawan: str
    kode_dept: Optional[str]
    sumber_jadwal: Optional[str]
    sudah_patroli: bool
    jumlah_sesi_patroli: int
    jam_patrol_terakhir: Optional[str]

class ReguSlot(BaseModel):
    jam_ke: int
    rentang: str
    mulai: str
    batas: str
    terpenuhi: bool
    jumlah_event: int
    petugas_patroli: List[Dict[str, str]]
    belum_patroli: List[Dict[str, str]]

class ReguGroup(BaseModel):
    uid: str
    kode_cabang: Optional[str]
    nama_cabang: Optional[str]
    kode_jam_kerja: str
    nama_jam_kerja: str
    jam_masuk: Optional[str]
    jam_pulang: Optional[str]
    lintashari: bool
    total_anggota: int
    sudah_patroli: int
    belum_patroli: int
    jumlah_sesi_patroli: int
    slot_wajib: int
    slot_terpenuhi: int
    slot_kurang: int
    persen_slot: float
    status_level: str
    shift_timing_status: str
    shift_timing_label: str
    members: List[ReguMember]
    hourly_slots: List[ReguSlot]

class MonitoringResponse(BaseModel):
    tanggal: str
    hari: str
    regu_groups: List[ReguGroup]
    summary: Dict[str, Any]

# --- Helpers ---

def get_hari_indonesia(d: date) -> str:
    days = {
        'Monday': 'Senin', 'Tuesday': 'Selasa', 'Wednesday': 'Rabu',
        'Thursday': 'Kamis', 'Friday': 'Jumat', 'Saturday': 'Sabtu', 'Sunday': 'Minggu'
    }
    return days.get(d.strftime("%A"), d.strftime("%A"))

def resolve_patrol_timestamp(p: PatrolSessions) -> Optional[datetime]:
    if not p.tanggal or not p.jam_patrol: return None
    return datetime.combine(p.tanggal, p.jam_patrol)

def build_shift_window(tgl: date, jam_masuk: time, jam_pulang: time, lintashari: bool):
    start = datetime.combine(tgl, jam_masuk)
    end = datetime.combine(tgl, jam_pulang)
    if lintashari or end <= start:
        end += timedelta(days=1)
    
    total_seconds = (end - start).total_seconds()
    total_hours = int((total_seconds + 3599) // 3600)
    return {'start': start, 'end': end, 'total_hours': max(1, total_hours)}

def is_patrol_in_window(p: PatrolSessions, window: dict, tgl: date) -> bool:
    ts = resolve_patrol_timestamp(p)
    if not ts: return False
    if not window: return ts.date() == tgl
    return window['start'] <= ts <= window['end']

# --- Main Logic ---

@router.get("", response_model=MonitoringResponse, dependencies=[Depends(require_permission_dependency("monitoringpatrol.index"))])
async def get_monitoring_regu(
    tanggal: Optional[date] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    kode_jam_kerja: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    # print(f"DEBUG: Processing monitoring regu for {tanggal}")
    tgl = tanggal or date.today()
    hari = get_hari_indonesia(tgl)
    
    # 1. Get Karyawan (Active)
    q_karyawan = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1')
    if kode_cabang:
        q_karyawan = q_karyawan.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        q_karyawan = q_karyawan.filter(Karyawan.kode_dept == kode_dept)
    karyawans = q_karyawan.all()
    
    if not karyawans:
        return MonitoringResponse(tanggal=str(tgl), hari=hari, regu_groups=[], summary={})

    nik_list = [k.nik for k in karyawans]
    
    # 2. Resolve Assignments
    # By Date
    by_date = db.query(SetJamKerjaByDate).filter(
        SetJamKerjaByDate.tanggal == tgl,
        SetJamKerjaByDate.nik.in_(nik_list)
    ).all()
    map_by_date = {x.nik: x.kode_jam_kerja for x in by_date}
    
    # By Day
    by_day = db.query(SetJamKerjaByDay).filter(
        SetJamKerjaByDay.hari == hari,
        SetJamKerjaByDay.nik.in_(nik_list)
    ).all()
    map_by_day = {x.nik: x.kode_jam_kerja for x in by_day}
    
    # By Dept
    # Join with Detail
    by_dept_rows = db.query(
        PresensiJamkerjaBydept.kode_cabang, 
        PresensiJamkerjaBydept.kode_dept, 
        PresensiJamkerjaBydeptDetail.kode_jam_kerja
    ).join(PresensiJamkerjaBydeptDetail, PresensiJamkerjaBydept.kode_jk_dept == PresensiJamkerjaBydeptDetail.kode_jk_dept)\
     .filter(PresensiJamkerjaBydeptDetail.hari == hari).all()
     
    map_by_dept = {} # Key: Cabang|Dept
    for r in by_dept_rows:
        key = f"{r.kode_cabang}|{r.kode_dept}"
        # Prioritize first match?
        if key not in map_by_dept: 
            map_by_dept[key] = r.kode_jam_kerja

    # Build assignments list
    assignments = []
    
    # Helper to resolve main
    resolved_main = {}
    
    for k in karyawans:
        code = map_by_date.get(k.nik)
        source = 'bydate'
        
        if not code:
            code = map_by_day.get(k.nik)
            source = 'byday'
            
        if not code:
            key = f"{k.kode_cabang}|{k.kode_dept}"
            code = map_by_dept.get(key)
            source = 'bydept'
            
        if code:
            resolved_main[k.nik] = code
            assignments.append({
                'nik': k.nik, 'nama': k.nama_karyawan, 'cabang': k.kode_cabang, 
                'dept': k.kode_dept, 'kode_jk': code, 'sumber': source
            })

    # Extra Assignments
    extras = db.query(PresensiJamkerjaBydateExtra).filter(
        PresensiJamkerjaBydateExtra.tanggal == tgl,
        PresensiJamkerjaBydateExtra.nik.in_(nik_list)
    ).all()
    map_extras = {x.nik: x.kode_jam_kerja for x in extras}
    
    for k in karyawans:
        extra_code = map_extras.get(k.nik)
        main_code = resolved_main.get(k.nik)
        if extra_code and extra_code != main_code:
            assignments.append({
                'nik': k.nik, 'nama': k.nama_karyawan, 'cabang': k.kode_cabang,
                'dept': k.kode_dept, 'kode_jk': extra_code, 'sumber': 'bydate_extra'
            })

    if not assignments:
        return MonitoringResponse(tanggal=str(tgl), hari=hari, regu_groups=[], summary={})

    # 3. Get Jam Kerja Info
    assign_codes = list(set([a['kode_jk'] for a in assignments]))
    jk_infos = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja.in_(assign_codes)).all()
    jk_map = {jk.kode_jam_kerja: jk for jk in jk_infos}
    
    cabang_infos = db.query(Cabang).all()
    cabang_map = {c.kode_cabang: c.nama_cabang for c in cabang_infos}
    
    # 4. Get Patrol Sessions
    # Window: Tgl - 1 to Tgl + 1
    d_start = tgl - timedelta(days=1)
    d_end = tgl + timedelta(days=1)
    
    patrols = db.query(PatrolSessions).filter(
        PatrolSessions.tanggal >= d_start,
        PatrolSessions.tanggal <= d_end,
        PatrolSessions.nik.in_([a['nik'] for a in assignments]),
        PatrolSessions.kode_jam_kerja.in_(assign_codes)
    ).all() # This could be large, but filtered by relevant people and codes

    # 5. Group assignemnts
    grouped = {} # Key: Cabang|KodeJK
    for a in assignments:
        key = f"{a['cabang']}|{a['kode_jk']}"
        if key not in grouped: grouped[key] = []
        grouped[key].append(a)
    
    # 6. Build Result
    regu_groups = []
    
    # Summary counters
    sum_total_members = 0
    sum_sudah = 0
    sum_belum = 0
    sum_slot_wajib = 0
    sum_slot_terpenuhi = 0
    sum_slot_kurang = 0

    for key, members in grouped.items():
        parts = key.split('|')
        cabang_code = parts[0]
        jk_code = parts[1]
        
        if kode_jam_kerja and jk_code != kode_jam_kerja:
            continue
        
        jk = jk_map.get(jk_code)
        
        # Build Window
        window = None
        lintashari = False
        if jk and jk.jam_masuk and jk.jam_pulang:
            lintashari = (str(jk.lintashari) == '1')
            window = build_shift_window(tgl, jk.jam_masuk, jk.jam_pulang, lintashari)
        
        if not window: continue # Skip invalid JK
        
        # Filter Patrols for this group
        group_patrols = []
        member_niks = set([m['nik'] for m in members])
        for p in patrols:
            if p.kode_jam_kerja == jk_code and p.nik in member_niks:
                if is_patrol_in_window(p, window, tgl):
                    group_patrols.append(p)
        
        # Determine Member Status
        member_stats = []
        sudah_count_local = 0
        
        # Map patrol by NIK
        p_by_nik = {}
        for p in group_patrols:
            if p.nik not in p_by_nik: p_by_nik[p.nik] = []
            p_by_nik[p.nik].append(p)
            
        for m in members:
            m_patrols = p_by_nik.get(m['nik'], [])
            sudah = len(m_patrols) > 0
            count = len(m_patrols)
            last = None
            if m_patrols:
                # find max by resolved timestamp
                m_patrols.sort(key=lambda x: resolve_patrol_timestamp(x) or datetime.min, reverse=True)
                last = str(m_patrols[0].jam_patrol)
            
            if sudah: sudah_count_local += 1
            
            member_stats.append(ReguMember(
                nik=m['nik'], nama_karyawan=m['nama'], kode_dept=m['dept'],
                sumber_jadwal=m['sumber'], sudah_patroli=sudah,
                jumlah_sesi_patroli=count, jam_patrol_terakhir=last
            ))
            
        total_mem = len(members)
        belum_count = total_mem - sudah_count_local
        
        # Slots Monitor
        # Simplify: Hourly Monitor only (Skip complex Schedule Monitor for now as I cannot port it easily in one shot)
        # Or better: Build hourly monitor based on window duration
        
        slots_data = []
        slot_wajib = 0
        slot_terpenuhi = 0
        
        start_dt = window['start']
        end_dt = window['end']
        current = start_dt
        jam_ke = 1
        
        while current < end_dt:
            slot_end = current + timedelta(hours=1)
            if slot_end > end_dt: slot_end = end_dt
            
            # Find events in this slot
            slot_events = [
                p for p in group_patrols 
                if resolve_patrol_timestamp(p) and current <= resolve_patrol_timestamp(p) <= slot_end
            ]
            
            terpenuhi = len(slot_events) > 0
            if terpenuhi: slot_terpenuhi += 1
            slot_wajib += 1 # Every hour is a slot
            
            # Petugas details
            p_niks = set([p.nik for p in slot_events])
            petugas = [{'nik': m.nik, 'nama': m.nama_karyawan} for m in member_stats if m.nik in p_niks]
            not_petugas = [{'nik': m.nik, 'nama': m.nama_karyawan} for m in member_stats if m.nik not in p_niks]

            slots_data.append(ReguSlot(
                jam_ke=jam_ke,
                rentang=f"{current.strftime('%H:%M')} - {slot_end.strftime('%H:%M')}",
                mulai=current.isoformat(),
                batas=slot_end.isoformat(),
                terpenuhi=terpenuhi,
                jumlah_event=len(slot_events),
                petugas_patroli=petugas,
                belum_patroli=not_petugas
            ))
            
            current = slot_end
            jam_ke += 1

        slot_kurang = max(0, slot_wajib - slot_terpenuhi)
        persen = 0.0
        if slot_wajib > 0: persen = round((slot_terpenuhi / slot_wajib) * 100, 1)

        # Status Level
        now_dt = datetime.now()
        shift_status = "sedang_berlangsung"
        shift_label = "Sedang Berlangsung"
        if now_dt > end_dt: 
            shift_status = "sudah_berlalu"
            shift_label = "Sudah Berlalu"
        elif now_dt < start_dt:
            shift_status = "belum_mulai"
            shift_label = "Belum Dimulai"
            
        status_level = "aman"
        if slot_kurang > 0: status_level = "perlu_tindak"

        # Cabang Name (Use code as fallback)
        c_name = cabang_map.get(cabang_code, cabang_code)
        
        regu_groups.append(ReguGroup(
            uid=key,
            kode_cabang=cabang_code,
            nama_cabang=c_name,
            kode_jam_kerja=jk_code,
            nama_jam_kerja=jk.nama_jam_kerja if jk else "-",
            jam_masuk=str(jk.jam_masuk) if jk and jk.jam_masuk else None,
            jam_pulang=str(jk.jam_pulang) if jk and jk.jam_pulang else None,
            lintashari=lintashari,
            total_anggota=total_mem,
            sudah_patroli=sudah_count_local,
            belum_patroli=belum_count,
            jumlah_sesi_patroli=len(group_patrols),
            slot_wajib=slot_wajib,
            slot_terpenuhi=slot_terpenuhi,
            slot_kurang=slot_kurang,
            persen_slot=persen,
            status_level=status_level,
            shift_timing_status=shift_status,
            shift_timing_label=shift_label,
            members=member_stats,
            hourly_slots=slots_data
        ))
        
        sum_total_members += total_mem
        sum_sudah += sudah_count_local
        sum_belum += belum_count
        sum_slot_wajib += slot_wajib
        sum_slot_terpenuhi += slot_terpenuhi
        sum_slot_kurang += slot_kurang

    # Sort groups
    regu_groups.sort(key=lambda x: x.kode_jam_kerja)
    
    total_persen = 0.0
    if sum_slot_wajib > 0: total_persen = round((sum_slot_terpenuhi / sum_slot_wajib) * 100, 1)

    summary = {
        'total_regu_shift': len(regu_groups),
        'total_anggota': sum_total_members,
        'total_sudah_patroli': sum_sudah,
        'total_belum_patroli': sum_belum,
        'total_slot_wajib': sum_slot_wajib,
        'total_slot_terpenuhi': sum_slot_terpenuhi,
        'total_slot_kurang': sum_slot_kurang,
        'persen_slot': total_persen
    }
    
    return MonitoringResponse(tanggal=str(tgl), hari=hari, regu_groups=regu_groups, summary=summary)
