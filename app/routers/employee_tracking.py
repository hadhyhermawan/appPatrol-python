from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, text, desc, and_, or_, case, literal_column
from app.database import get_db
from app.models.models import (
    Karyawan, Cabang, Presensi, PresensiJamkerja, 
    EmployeeLocations, EmployeeStatus, EmployeeLocationHistories
)
from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime, date, time, timedelta

router = APIRouter(
    prefix="/api/employee-tracking",
    tags=["Employee Tracking"],
    responses={404: {"description": "Not found"}},
)

# Pydantic Models for Response
class EmployeeTrackingDTO(BaseModel):
    nik: str
    nama_karyawan: str
    kode_cabang: Optional[str]
    nama_cabang: Optional[str]
    lokasi_cabang: Optional[str]
    radius_cabang: Optional[int]
    latitude: Optional[float]
    longitude: Optional[float]
    is_mocked: Optional[int]
    provider: Optional[str]
    is_online: int
    battery_level: Optional[int]
    is_charging: int
    last_seen: Optional[datetime]
    menit_lalu: Optional[int]
    
    active_presensi_id: Optional[int]
    active_presensi_tanggal: Optional[date]
    active_jam_in: Optional[time]
    active_kode_jam_kerja: Optional[str]
    active_nama_jam_kerja: Optional[str]
    active_shift_masuk: Optional[time]
    active_shift_pulang: Optional[time]
    active_shift_lintashari: Optional[str] # char(1) in db

    # Front-end helper fields (calculated in python)
    has_active_shift_tracking: bool = False
    office_radius_meter: Optional[int] = None
    distance_to_office_meter: Optional[int] = None
    is_outside_office_radius: Optional[bool] = None
    radius_status_label: str = "Belum Absen Masuk"
    radius_status_tone: str = "secondary"
    
    shift_label: str = "-"
    is_shift_passed: bool = False
    shift_status_label: str = "Tidak Ada Shift Aktif"
    shift_status_tone: str = "secondary"
    shift_start_at: Optional[datetime] = None
    shift_end_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class HistoryDTO(BaseModel):
    id: int
    nik: str
    latitude: float
    longitude: float
    recorded_at: datetime
    is_mocked: int
    speed: Optional[float]
    accuracy: Optional[float]

    class Config:
        from_attributes = True

def haversine_distance(lat1, lon1, lat2, lon2):
    import math
    R = 6371000  # radius of Earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    d = R * c
    return d

@router.get("/map-data", response_model=dict)
async def get_map_data(
    kode_cabang: Optional[str] = Query(None),
    kode_jadwal: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    is_online: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        # Subquery for latest open presensi
        # Equivalent to: 
        # SELECT p.nik, MAX(p.id) as latest_id FROM presensi p 
        # WHERE p.jam_in IS NOT NULL AND p.jam_out IS NULL AND p.status='h' AND p.kode_jam_kerja IS NOT NULL 
        # GROUP BY p.nik
        
        latest_presensi_sub = db.query(
            Presensi.nik, 
            func.max(Presensi.id).label('latest_id')
        ).filter(
            Presensi.jam_in.isnot(None),
            Presensi.jam_out.is_(None),
            Presensi.status == 'h',
            Presensi.kode_jam_kerja.isnot(None)
        ).group_by(Presensi.nik).subquery()

        # Main Query
        # Join Karyawan -> Cabang, EmployeeLocations, EmployeeStatus
        # Join LatestPresensiSub -> Presensi -> PresensiJamkerja
        
        query = db.query(
            Karyawan.nik,
            Karyawan.nama_karyawan,
            Karyawan.kode_cabang,
            Cabang.nama_cabang,
            Cabang.lokasi_cabang,
            Cabang.radius_cabang,
            EmployeeLocations.latitude,
            EmployeeLocations.longitude,
            EmployeeLocations.is_mocked,
            EmployeeLocations.provider,
            EmployeeStatus.is_online, # We might need to recalc based on last_seen if 0/1 isn't reliable enough, but trust DB for now
            EmployeeStatus.battery_level,
            EmployeeStatus.is_charging,
            EmployeeStatus.last_seen,
            Presensi.id.label('active_presensi_id'),
            Presensi.tanggal.label('active_presensi_tanggal'),
            Presensi.jam_in.label('active_jam_in'),
            Presensi.kode_jam_kerja.label('active_kode_jam_kerja'),
            PresensiJamkerja.nama_jam_kerja.label('active_nama_jam_kerja'),
            PresensiJamkerja.jam_masuk.label('active_shift_masuk'),
            PresensiJamkerja.jam_pulang.label('active_shift_pulang'),
            PresensiJamkerja.lintashari.label('active_shift_lintashari')
        ).select_from(Karyawan)\
        .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
        .outerjoin(EmployeeLocations, Karyawan.nik == EmployeeLocations.nik)\
        .outerjoin(EmployeeStatus, Karyawan.nik == EmployeeStatus.nik)\
        .outerjoin(latest_presensi_sub, Karyawan.nik == latest_presensi_sub.c.nik)\
        .outerjoin(Presensi, Presensi.id == latest_presensi_sub.c.latest_id)\
        .outerjoin(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)

        # Filters
        # Only those with locations and active shift
        query = query.filter(
            EmployeeLocations.latitude.isnot(None),
            EmployeeLocations.longitude.isnot(None),
            Presensi.id.isnot(None),
            Presensi.kode_jam_kerja.isnot(None),
            PresensiJamkerja.kode_jam_kerja.isnot(None)
        )

        if kode_cabang:
            # Simple check, exact match or like name
            query = query.filter(or_(
                Karyawan.kode_cabang == kode_cabang,
                func.lower(Cabang.nama_cabang).like(f"%{kode_cabang.lower()}%")
            ))
        
        if kode_jadwal:
            query = query.filter(Presensi.kode_jam_kerja == kode_jadwal)

        if q:
            search_term = q.lower().strip()
            query = query.filter(or_(
                func.lower(Karyawan.nama_karyawan).like(f"%{search_term}%"),
                Karyawan.nik.like(f"%{search_term}%"),
                func.lower(Cabang.nama_cabang).like(f"%{search_term}%")
            ))

        if is_online in ['0', '1']:
            # Also check last_seen logic if needed. PHP: CASE WHEN es.last_seen >= NOW() - INTERVAL 1 HOUR THEN 1 ELSE 0 END
            # We can replicate that in python post-processing or SQL
            # Let's trust is_online column for now, or filter by it
            query = query.filter(EmployeeStatus.is_online == int(is_online))

        results = query.order_by(Karyawan.nama_karyawan).all()

        data_list = []
        for row in results:
            # Map Row to DTO
            # Note: SQLAlchemy rows are named tuples or Row objects
            
            # Recalculate is_online based on last_seen (1 hour threshold) like PHP
            is_online_calc = 0
            if row.last_seen:
                diff = datetime.now() - row.last_seen
                if diff.total_seconds() < 3600:
                    is_online_calc = 1
            
            menit_lalu = 0
            if row.last_seen:
                diff = datetime.now() - row.last_seen
                menit_lalu = int(diff.total_seconds() / 60)

            def normalize_time_val(val):
                if isinstance(val, timedelta):
                    total_seconds = int(val.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    return time(hours, minutes, seconds)
                return val

            active_shift_masuk_normalized = normalize_time_val(row.active_shift_masuk)
            active_shift_pulang_normalized = normalize_time_val(row.active_shift_pulang)
            
            # active_jam_in comes from Presensi.jam_in which is DateTime in model, but DTO expects time
            active_jam_in_val = row.active_jam_in
            if isinstance(active_jam_in_val, datetime):
                active_jam_in_val = active_jam_in_val.time()

            dto = EmployeeTrackingDTO(
                nik=row.nik,
                nama_karyawan=row.nama_karyawan,
                kode_cabang=row.kode_cabang,
                nama_cabang=row.nama_cabang,
                lokasi_cabang=row.lokasi_cabang,
                radius_cabang=row.radius_cabang,
                latitude=float(row.latitude) if row.latitude else None,
                longitude=float(row.longitude) if row.longitude else None,
                is_mocked=row.is_mocked,
                provider=row.provider,
                is_online=is_online_calc, 
                battery_level=row.battery_level,
                is_charging=row.is_charging or 0,
                last_seen=row.last_seen,
                menit_lalu=menit_lalu,
                active_presensi_id=row.active_presensi_id,
                active_presensi_tanggal=row.active_presensi_tanggal,
                active_jam_in=active_jam_in_val,
                active_kode_jam_kerja=row.active_kode_jam_kerja,
                active_nama_jam_kerja=row.active_nama_jam_kerja,
                active_shift_masuk=active_shift_masuk_normalized,
                active_shift_pulang=active_shift_pulang_normalized,
                active_shift_lintashari=row.active_shift_lintashari
            )

            # --- Logic from appendOfficeRadiusStatus ---
            dto.has_active_shift_tracking = bool(row.active_presensi_id)
            dto.office_radius_meter = int(row.radius_cabang) if row.radius_cabang else None
            
            # Shift Logic
            shiftName = row.active_nama_jam_kerja or ""
            shiftCode = row.active_kode_jam_kerja or ""
            if shiftCode and shiftName:
                dto.shift_label = f"{shiftCode} - {shiftName}"
            elif shiftCode:
                dto.shift_label = shiftCode
            elif shiftName:
                dto.shift_label = shiftName
            
            if dto.has_active_shift_tracking and row.active_presensi_tanggal and active_shift_masuk_normalized and active_shift_pulang_normalized:
                # Build Shift Window
                start_dt = datetime.combine(row.active_presensi_tanggal, active_shift_masuk_normalized)
                end_dt = datetime.combine(row.active_presensi_tanggal, active_shift_pulang_normalized)
                if str(row.active_shift_lintashari) == '1' or end_dt <= start_dt:
                    end_dt += timedelta(days=1)
                
                dto.shift_start_at = start_dt
                dto.shift_end_at = end_dt
                
                now = datetime.now()
                if now > end_dt:
                    dto.is_shift_passed = True
                    dto.shift_status_label = 'Shift Sudah Lewat'
                    dto.shift_status_tone = 'warning'
                elif now < start_dt:
                    dto.shift_status_label = 'Shift Belum Mulai'
                    dto.shift_status_tone = 'info'
                else:
                    dto.shift_status_label = 'Dalam Jam Shift'
                    dto.shift_status_tone = 'success'
            else:
                 dto.shift_status_label = 'Tidak Ada Shift Aktif' if not dto.has_active_shift_tracking else 'Window Shift Tidak Valid'

            # Radius Logic
            if dto.latitude is not None and dto.longitude is not None and row.lokasi_cabang and dto.office_radius_meter:
                 parts = row.lokasi_cabang.split(',')
                 if len(parts) >= 2:
                     try:
                         office_lat = float(parts[0].strip())
                         office_lng = float(parts[1].strip())
                         dist = haversine_distance(office_lat, office_lng, dto.latitude, dto.longitude)
                         dto.distance_to_office_meter = int(dist)
                         dto.is_outside_office_radius = dto.distance_to_office_meter > dto.office_radius_meter
                         
                         if dto.is_outside_office_radius:
                             dto.radius_status_label = 'Di Luar Radius Kantor'
                             dto.radius_status_tone = 'danger'
                         else:
                             dto.radius_status_label = 'Di Dalam Radius Kantor'
                             dto.radius_status_tone = 'success'
                     except:
                         dto.radius_status_label = 'Lokasi kantor invalid'
            elif dto.latitude is None:
                dto.radius_status_label = 'Lokasi belum terbaca'
                dto.radius_status_tone = 'warning'
            else:
                dto.radius_status_label = 'Lokasi/radius kantor belum disetting'

            data_list.append(dto)

        return {
            "status": True,
            "data": data_list
        }

    except Exception as e:
        print(f"Error map-data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{nik}/history", response_model=List[HistoryDTO])
async def get_history(
    nik: str,
    db: Session = Depends(get_db)
):
    try:
        # Cleanup old history first (optional, maybe skip or do async)
        # DELETE FROM employee_location_histories WHERE recorded_at < NOW() - INTERVAL 1 DAY
        # Skip for now to keep read-only fast
        
        histories = db.query(EmployeeLocationHistories)\
            .filter(EmployeeLocationHistories.nik == nik)\
            .order_by(desc(EmployeeLocationHistories.recorded_at))\
            .limit(100)\
            .all()
        
        return histories
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
