from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_, and_
from app.database import get_db
from app.models.models import (
    Karyawan, Presensi, Cabang, EmployeeLocations,
    PresensiIzinabsen, PresensiIzinsakit, PresensiIzincuti, PresensiIzindinas, Lembur
)
from datetime import datetime, date, timedelta
import math

router = APIRouter(
    prefix="/api/security/notifications",  # Updated prefix
    tags=["Notifications"],
    responses={404: {"description": "Not found"}},
)

def get_excluded_niks(db: Session):
    """
    Get list of NIKs that should be excluded from security alerts.
    Roles excluded:
    1. Super Admin
    2. Admin Departemen
    3. Unit Pelaksana Pelayanan Pelanggan
    4. Unit Layanan Pelanggan
    """
    excluded_roles = [
        "Super Admin", 
        "Admin Departemen", 
        "Unit Pelaksana Pelayanan Pelanggan", 
        "Unit Layanan Pelanggan"
    ]
    
    # Query to fetch NIKs associated with these roles
    # Adapting schema: Karyawan <-> users_karyawan <-> ModelHasRoles <-> Roles
    try:
        query = text("""
            SELECT uk.nik 
            FROM users_karyawan uk
            JOIN model_has_roles mhr ON uk.id_user = mhr.model_id
            JOIN roles r ON mhr.role_id = r.id
            WHERE mhr.model_type = 'App\\\\Models\\\\User'
            AND r.name IN :roles
        """)
        
        result = db.execute(query, {"roles": tuple(excluded_roles)}).fetchall()
        return [row[0] for row in result]
    except Exception as e:
        print(f"Error fetching excluded NIKs: {e}")
        return []

@router.get("/summary")
def get_notification_summary(db: Session = Depends(get_db)):
    excluded_niks = get_excluded_niks(db)

    # 1. Izin & Lembur (Pending Approval)
    notifikasi_izinabsen = db.query(PresensiIzinabsen).filter(PresensiIzinabsen.status == '0').count()
    notifikasi_izinsakit = db.query(PresensiIzinsakit).filter(PresensiIzinsakit.status == '0').count()
    notifikasi_izincuti = db.query(PresensiIzincuti).filter(PresensiIzincuti.status == '0').count()
    notifikasi_izindinas = db.query(PresensiIzindinas).filter(PresensiIzindinas.status == '0').count()
    notifikasi_lembur = db.query(Lembur).filter(Lembur.status == '0').count()
    
    total_ajuan_absen = notifikasi_izinabsen + notifikasi_izinsakit + notifikasi_izincuti + notifikasi_izindinas

    # 2. Device Lock
    q_device = db.query(Karyawan).filter(Karyawan.lock_device_login == 1)
    if excluded_niks:
        q_device = q_device.filter(Karyawan.nik.notin_(excluded_niks))
    device_lock_count = q_device.count()
    
    # 3. Expiring Member (<= 30 days)
    today = date.today()
    next_30_days = today + timedelta(days=30)
    
    q_expiring = db.query(Karyawan).filter(
        Karyawan.masa_aktif_kartu_anggota >= today,
        Karyawan.masa_aktif_kartu_anggota <= next_30_days
    )
    if excluded_niks:
        q_expiring = q_expiring.filter(Karyawan.nik.notin_(excluded_niks))
    expiring_count = q_expiring.count()

    # 4. Mock Location (Realtime from EmployeeLocations)
    q_mock = db.query(EmployeeLocations).filter(EmployeeLocations.is_mocked == 1)
    if excluded_niks:
        q_mock = q_mock.filter(EmployeeLocations.nik.notin_(excluded_niks))
    mock_count = q_mock.count()

    # 5. Radius Violation (Active Shift & Out of Radius)
    # Get active presensi (checked in, not checked out)
    q_active = db.query(Presensi.lokasi_in, Karyawan.nik, Cabang.lokasi_cabang, Cabang.radius_cabang) \
        .join(Karyawan, Presensi.nik == Karyawan.nik) \
        .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang) \
        .filter(
            Presensi.tanggal == today,
            Presensi.jam_in != None,
            Presensi.jam_out == None,
            Presensi.lokasi_in != None,
            Cabang.lokasi_cabang != None,
            Cabang.radius_cabang > 0,
            Karyawan.lock_location == '1'
        )
    
    if excluded_niks:
        q_active = q_active.filter(Karyawan.nik.notin_(excluded_niks))
        
    active_presensi = q_active.all()

    radius_violation_count = 0
    for p in active_presensi:
        try:
            user_lat, user_long = map(float, p.lokasi_in.split(','))
            office_lat, office_long = map(float, p.lokasi_cabang.split(','))
            
            # Haversine Formula
            R = 6371000 
            dLat = math.radians(office_lat - user_lat)
            dLon = math.radians(office_long - user_long)
            a = math.sin(dLat/2) * math.sin(dLat/2) + \
                math.cos(math.radians(user_lat)) * math.cos(math.radians(office_lat)) * \
                math.sin(dLon/2) * math.sin(dLon/2)
            c_val = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = R * c_val
            
            if distance > p.radius_cabang:
                radius_violation_count += 1
        except:
            continue

    return {
        "ajuan_absen": total_ajuan_absen,
        "lembur": notifikasi_lembur,
        "device_lock": device_lock_count,
        "member_expiring": expiring_count,
        "mock_location": mock_count,
        "radius_violation": radius_violation_count,
        "total_security_alerts": device_lock_count + mock_count + radius_violation_count,
        "total_approval_pending": total_ajuan_absen + notifikasi_lembur
    }

@router.get("/security-alerts")
def get_security_alerts_detail(db: Session = Depends(get_db)):
    """Get Top 5 Details for each security alert category"""
    excluded_niks = get_excluded_niks(db)
    
    # Mock Locations
    q_mocks = db.query(
        Karyawan.nik, Karyawan.nama_karyawan, Cabang.nama_cabang, EmployeeLocations.updated_at
    ).join(EmployeeLocations, Karyawan.nik == EmployeeLocations.nik)\
     .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
     .filter(EmployeeLocations.is_mocked == 1)
     
    if excluded_niks:
        q_mocks = q_mocks.filter(Karyawan.nik.notin_(excluded_niks))
        
    mocks = q_mocks.order_by(EmployeeLocations.updated_at.desc()).limit(5).all()
     
    mock_data = [{
        "nik": m.nik, 
        "nama": m.nama_karyawan, 
        "cabang": m.nama_cabang, 
        "time": m.updated_at,
        "type": "FAKE_GPS"
    } for m in mocks]

    # Radius Violations (Re-run logic, limited to 5)
    today = date.today()
    q_active = db.query(Presensi.lokasi_in, Presensi.jam_in, Karyawan.nik, Karyawan.nama_karyawan, Cabang.nama_cabang, Cabang.lokasi_cabang, Cabang.radius_cabang) \
        .join(Karyawan, Presensi.nik == Karyawan.nik) \
        .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang) \
        .filter(
            Presensi.tanggal == today,
            Presensi.jam_in != None,
            Presensi.jam_out == None,
            Presensi.lokasi_in != None,
            Cabang.lokasi_cabang != None,
            Cabang.radius_cabang > 0,
            Karyawan.lock_location == '1'
        )
        
    if excluded_niks:
        q_active = q_active.filter(Karyawan.nik.notin_(excluded_niks))

    active_presensi = q_active.limit(50).all() # Limit first to avoid heavy calc

    radius_data = []
    for p in active_presensi:
        try:
            # Handle jam_in (might be datetime or time)
            time_val = None
            if p.jam_in:
                if isinstance(p.jam_in, datetime):
                    time_val = p.jam_in
                else: 
                    # Assuming it is time object
                    time_val = datetime.combine(today, p.jam_in)

            user_lat, user_long = map(float, p.lokasi_in.split(','))
            office_lat, office_long = map(float, p.lokasi_cabang.split(','))
            
            # Haversine Formula
            R = 6371000 
            dLat = math.radians(office_lat - user_lat)
            dLon = math.radians(office_long - user_long)
            a = math.sin(dLat/2) * math.sin(dLat/2) + \
                math.cos(math.radians(user_lat)) * math.cos(math.radians(office_lat)) * \
                math.sin(dLon/2) * math.sin(dLon/2)
            c_val = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = R * c_val
            
            if distance > p.radius_cabang:
                radius_data.append({
                    "nik": p.nik,
                    "nama": p.nama_karyawan,
                    "cabang": p.nama_cabang,
                    "time": time_val,
                    "type": "OUT_OF_LOCATION",
                    "distance": int(distance),
                    "radius": p.radius_cabang
                })
                if len(radius_data) >= 5: break
        except Exception as e:
            print(f"Error processing radius violation for {p.nik}: {e}")
            continue

    # Device Logic
    q_device = db.query(Karyawan.nik, Karyawan.nama_karyawan, Cabang.nama_cabang)\
                 .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
                 .filter(Karyawan.lock_device_login == 1)
    if excluded_niks:
        q_device = q_device.filter(Karyawan.nik.notin_(excluded_niks))
    
    devices = q_device.limit(5).all()
    device_data = [{
        "nik": d.nik,
        "nama": d.nama_karyawan,
        "cabang": d.nama_cabang,
        "type": "DEVICE_LOCK",
        "time": None
    } for d in devices]

    # Member Expiring
    next_30_days = today + timedelta(days=30)
    q_expiring = db.query(Karyawan.nik, Karyawan.nama_karyawan, Cabang.nama_cabang, Karyawan.masa_aktif_kartu_anggota)\
                 .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
                 .filter(
                    Karyawan.masa_aktif_kartu_anggota >= today,
                    Karyawan.masa_aktif_kartu_anggota <= next_30_days
                 )
    if excluded_niks:
        q_expiring = q_expiring.filter(Karyawan.nik.notin_(excluded_niks))
        
    expiring = q_expiring.limit(5).all()
    expiring_data = [{
        "nik": e.nik,
        "nama": e.nama_karyawan,
        "cabang": e.nama_cabang,
        "type": "MEMBER_EXPIRING",
        "time": datetime.combine(e.masa_aktif_kartu_anggota, datetime.min.time()) if e.masa_aktif_kartu_anggota else None
    } for e in expiring]

    return {
        "mock_locations": mock_data,
        "radius_violations": radius_data,
        "device_locks": device_data,
        "member_expiring": expiring_data
    }
