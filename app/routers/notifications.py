from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_, and_
from app.database import get_db
from app.models.models import (
    Karyawan, Presensi, Cabang, EmployeeLocations,
    PresensiIzinabsen, PresensiIzinsakit, PresensiIzincuti, PresensiIzindinas, Lembur,
    KaryawanDevices, WalkieRtcMessages
)
from app.core.permissions import get_current_user, CurrentUser
from pydantic import BaseModel
from datetime import datetime, date, timedelta
import math
import requests
import json

# Hardcoded for now based on Laravel .env inspection
FCM_SERVER_KEY = "AIzaSyAxxxb6jx50Ow1PiF517jglXk4kvnt6vBc"

router = APIRouter(
    prefix="/api",
    tags=["Notifications"],
    responses={404: {"description": "Not found"}},
)

# ==============================================================================
# ORIGINAL NOTIFICATION LOGIC (Security Alerts etc)
# ==============================================================================

def get_excluded_niks(db: Session):
    """
    Get list of NIKs that should be excluded from security alerts.
    """
    excluded_roles = [
        "Super Admin", 
        "Admin Departemen", 
        "Unit Pelaksana Pelayanan Pelanggan", 
        "Unit Layanan Pelanggan"
    ]
    
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

@router.get("/security/notifications/summary")
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

@router.get("/security/notifications/security-alerts")
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

    # Radius Violations
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

    active_presensi = q_active.limit(50).all()

    radius_data = []
    for p in active_presensi:
        try:
            time_val = None
            if p.jam_in:
                if isinstance(p.jam_in, datetime):
                    time_val = p.jam_in
                else: 
                    time_val = datetime.combine(today, p.jam_in)

            user_lat, user_long = map(float, p.lokasi_in.split(','))
            office_lat, office_long = map(float, p.lokasi_cabang.split(','))
            
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

# ==============================================================================
# NEW NOTIFICATION LOGIC (Video Call, FCM Token)
# ==============================================================================

class StartCallRequest(BaseModel):
    room_id: str
    caller_name: str = None

@router.post("/video-call/start")
async def start_video_call(
    payload: StartCallRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    room_id = payload.room_id
    caller_name = payload.caller_name
    
    # FETCH NIK MANUALLY
    nik = None
    if current_user.username.isdigit() and len(current_user.username) > 5:
        nik = current_user.username
    else:
        kary = db.query(Karyawan).filter(Karyawan.nik == current_user.username).first()
        if kary:
            nik = kary.nik
            
    sender_id = nik or current_user.username
    
    try:
        print(f"DEBUG VIDEO CALL: Start requested for room {room_id} by {sender_id}")

        # 1. Identify Participants
        target_niks = []
        
        # A. Check if room is a defined Walkie Channel
        from app.models.models import WalkieChannels, WalkieChannelCabangs
        channel = db.query(WalkieChannels).filter(WalkieChannels.code == room_id).first()
        
        if channel:
            # Query eligible employees
            query = db.query(Karyawan.nik).filter(Karyawan.status_karyawan == '1')
            
            # Filter by Dept if specified
            if channel.dept_members:
                depts = [d.strip() for d in channel.dept_members.split(',')]
                query = query.filter(Karyawan.kode_dept.in_(depts))
                
            # Filter by Cabang if linked
            channel_cabangs = db.query(WalkieChannelCabangs).filter(WalkieChannelCabangs.walkie_channel_id == channel.id).all()
            if channel_cabangs:
                 cabangs = [cc.kode_cabang for cc in channel_cabangs]
                 query = query.filter(Karyawan.kode_cabang.in_(cabangs))
            
            results = query.all()
            target_niks = [r[0] for r in results if r[0] != sender_id]
            print(f"DEBUG VIDEO CALL: Found {len(target_niks)} participants via Channel rules.")
            
        # B. Fallback to Message History
        if not target_niks:
            participant_niks = db.query(WalkieRtcMessages.sender_id)\
                                 .filter(WalkieRtcMessages.room == room_id)\
                                 .distinct().all()
            target_niks = [row[0] for row in participant_niks if row[0] != sender_id]
            print(f"DEBUG VIDEO CALL: Found {len(target_niks)} participants via History.")
        
        if not target_niks:
            return {"status": False, "message": "No accessible participants found in this room history"}

        # 2. Get FCM Tokens
        devices = db.query(KaryawanDevices)\
                    .filter(KaryawanDevices.nik.in_(target_niks))\
                    .all()
                    
        tokens = [d.fcm_token for d in devices if d.fcm_token]
        
        if not tokens:
             return {"status": False, "message": "No target devices found"}

        # 3. Send FCM Notification
        headers = {
            "Authorization": f"key={FCM_SERVER_KEY}",
            "Content-Type": "application/json"
        }
        
        actual_caller_name = caller_name
        if not actual_caller_name:
            karyawan = db.query(Karyawan).filter(Karyawan.nik == sender_id).first()
            actual_caller_name = karyawan.nama_karyawan if karyawan else current_user.username

        success_count = 0
        failure_count = 0
        
        for token in tokens:
            payload = {
                "to": token,
                "priority": "high",
                "data": {
                    "type": "video_call_offer",
                    "room": room_id,
                    "caller_name": actual_caller_name,
                    "ttl": "60s"
                },
            }
            
            try:
                response = requests.post("https://fcm.googleapis.com/fcm/send", headers=headers, json=payload, timeout=5)
                if response.status_code == 200:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
                
        return {
            "status": True, 
            "message": f"Call started. Notified {success_count} devices.",
            "targets": len(target_niks)
        }

    except Exception as e:
        print(f"Error starting video call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/firebase/token")
async def save_fcm_token(
    payload: dict = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        token = payload.get("token") or payload.get("fcm_token")
        if not token:
             return {"status": False, "message": "Token missing"}
             
        # FETCH NIK MANUALLY
        nik = None
        if current_user.username.isdigit() and len(current_user.username) > 5:
            nik = current_user.username
        else:
            kary = db.query(Karyawan).filter(Karyawan.nik == current_user.username).first()
            if kary:
                nik = kary.nik
                
        if not nik:
             return {"status": False, "message": "User NIK not found"}

        # Check existing
        device = db.query(KaryawanDevices).filter(KaryawanDevices.fcm_token == token).first()
        
        if device:
             if device.nik != nik:
                 device.nik = nik
                 device.updated_at = datetime.now()
                 db.commit()
        else:
             new_device = KaryawanDevices(
                 nik=nik,
                 fcm_token=token,
                 device_type='android',
                 created_at=datetime.now(),
                 updated_at=datetime.now()
             )
             db.add(new_device)
             db.commit()
             
        return {"status": True, "message": "Token saved"}
        
    except Exception as e:
        print(f"Error saving FCM token: {e}")
        raise HTTPException(status_code=500, detail=str(e))
