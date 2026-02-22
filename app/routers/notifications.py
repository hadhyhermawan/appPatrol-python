from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import func, text, or_, and_
from app.database import get_db
from app.models.models import (
    Karyawan, Presensi, Cabang, EmployeeLocations,
    PresensiIzinabsen, PresensiIzinsakit, PresensiIzincuti, PresensiIzindinas, Lembur,
    KaryawanDevices, WalkieRtcMessages, SecurityReports
)
from app.core.permissions import get_current_user
# from app.core.permissions import CurrentUser # Legacy uses different CurrentUser model
from app.routers.auth_legacy import get_current_user_sanctum, CurrentUser # Use legacy auth for Sanctum support
from pydantic import BaseModel
from datetime import datetime, date, timedelta
import math
import requests
import json
import firebase_admin
from firebase_admin import credentials, messaging

# Initialize Firebase Admin SDK
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("/var/www/appPatrol-python/serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    print("Firebase Admin SDK Initialized")
except Exception as e:
    print(f"Failed to initialize Firebase Admin SDK: {e}")

# FCM_SERVER_KEY removed as we use service account now


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
    q_outloc = db.query(SecurityReports).filter(SecurityReports.type == 'OUT_OF_LOCATION', SecurityReports.status_flag == 'pending')
    if excluded_niks:
        q_outloc = q_outloc.filter(SecurityReports.nik.notin_(excluded_niks))
    radius_violation_count = q_outloc.count()

    # 6. Force Close Reports
    q_force_close = db.query(SecurityReports).filter(SecurityReports.type == 'APP_FORCE_CLOSE', SecurityReports.status_flag == 'pending')
    if excluded_niks:
        q_force_close = q_force_close.filter(SecurityReports.nik.notin_(excluded_niks))
    force_close_count = q_force_close.count()

    # 7. Face Verify Fails
    q_face_fail = db.query(SecurityReports).filter(SecurityReports.type == 'FACE_VERIFICATION_FAILED', SecurityReports.status_flag == 'pending')
    if excluded_niks:
        q_face_fail = q_face_fail.filter(SecurityReports.nik.notin_(excluded_niks))
    face_fail_count = q_face_fail.count()

    # 8. Fake GPS (from SecurityReports)
    q_fake_gps = db.query(SecurityReports).filter(SecurityReports.type == 'FAKE_GPS', SecurityReports.status_flag == 'pending')
    if excluded_niks:
        q_fake_gps = q_fake_gps.filter(SecurityReports.nik.notin_(excluded_niks))
    fake_gps_count = q_fake_gps.count()

    # 9. Radius Bypass Requests
    q_bypass = db.query(SecurityReports).filter(SecurityReports.type == 'RADIUS_BYPASS', SecurityReports.status_flag == 'pending')
    if excluded_niks:
        q_bypass = q_bypass.filter(SecurityReports.nik.notin_(excluded_niks))
    bypass_count = q_bypass.count()

    return {
        "ajuan_absen": total_ajuan_absen,
        "lembur": notifikasi_lembur,
        "device_lock": device_lock_count,
        "member_expiring": expiring_count,
        "mock_location": mock_count,
        "radius_violation": radius_violation_count,
        "force_close": force_close_count,
        "face_verify_fail": face_fail_count,
        "fake_gps_alert": fake_gps_count,
        "radius_bypass_request": bypass_count,
        "total_security_alerts": device_lock_count + mock_count + radius_violation_count + force_close_count + face_fail_count + fake_gps_count + bypass_count,
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
    q_outloc = db.query(SecurityReports.id, SecurityReports.nik, Karyawan.nama_karyawan, Cabang.nama_cabang, SecurityReports.detail, SecurityReports.created_at)\
             .join(Karyawan, SecurityReports.nik == Karyawan.nik)\
             .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
             .filter(SecurityReports.type == 'OUT_OF_LOCATION', SecurityReports.status_flag == 'pending')\
             .order_by(SecurityReports.created_at.desc())
             
    if excluded_niks:
        q_outloc = q_outloc.filter(SecurityReports.nik.notin_(excluded_niks))
        
    outloc_alerts = q_outloc.limit(5).all()

    radius_data = []
    for p in outloc_alerts:
        distance_val = 0
        try:
             import re
             m = re.search(r'Jarak:\s*(\d+)m', str(p.detail))
             if m: distance_val = int(m.group(1))
        except:
             pass
             
        radius_data.append({
            "id": p.id,
            "nik": p.nik,
            "nama": p.nama_karyawan,
            "cabang": p.nama_cabang,
            "time": p.created_at,
            "type": "OUT_OF_LOCATION",
            "distance": distance_val,
            "radius": 0
        })

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
    today = date.today()
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

    # Force Closes
    q_fc = db.query(SecurityReports.id, SecurityReports.nik, Karyawan.nama_karyawan, Cabang.nama_cabang, SecurityReports.created_at)\
             .join(Karyawan, SecurityReports.nik == Karyawan.nik)\
             .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
             .filter(SecurityReports.type == 'APP_FORCE_CLOSE', SecurityReports.status_flag == 'pending')\
             .order_by(SecurityReports.created_at.desc())
    if excluded_niks:
        q_fc = q_fc.filter(SecurityReports.nik.notin_(excluded_niks))
    force_closes = q_fc.limit(5).all()
    fc_data = [{
        "id": f.id,
        "nik": f.nik,
        "nama": f.nama_karyawan,
        "cabang": f.nama_cabang,
        "type": "APP_FORCE_CLOSE",
        "time": f.created_at
    } for f in force_closes]

    # Face Verify Fails
    q_fv = db.query(SecurityReports.id, SecurityReports.nik, Karyawan.nama_karyawan, Cabang.nama_cabang, SecurityReports.created_at)\
             .join(Karyawan, SecurityReports.nik == Karyawan.nik)\
             .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
             .filter(SecurityReports.type == 'FACE_VERIFICATION_FAILED', SecurityReports.status_flag == 'pending')\
             .order_by(SecurityReports.created_at.desc())
    if excluded_niks:
        q_fv = q_fv.filter(SecurityReports.nik.notin_(excluded_niks))
    face_fails = q_fv.limit(5).all()
    fv_data = [{
        "id": f.id,
        "nik": f.nik,
        "nama": f.nama_karyawan,
        "cabang": f.nama_cabang,
        "type": "FACE_VERIFY_FAIL",
        "time": f.created_at
    } for f in face_fails]

    # Fake GPS Alerts (Detailed)
    q_fg = db.query(SecurityReports.id, SecurityReports.nik, Karyawan.nama_karyawan, Cabang.nama_cabang, SecurityReports.created_at)\
             .join(Karyawan, SecurityReports.nik == Karyawan.nik)\
             .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
             .filter(SecurityReports.type == 'FAKE_GPS', SecurityReports.status_flag == 'pending')\
             .order_by(SecurityReports.created_at.desc())
    if excluded_niks:
        q_fg = q_fg.filter(SecurityReports.nik.notin_(excluded_niks))
    fake_gps_alerts_raw = q_fg.limit(5).all()
    fg_data = [{
        "id": f.id,
        "nik": f.nik,
        "nama": f.nama_karyawan,
        "cabang": f.nama_cabang,
        "type": "FAKE_GPS_ALERT",
        "time": f.created_at
    } for f in fake_gps_alerts_raw]

    # Radius Bypass Requests
    q_rb = db.query(SecurityReports.id, SecurityReports.nik, Karyawan.nama_karyawan, Cabang.nama_cabang, SecurityReports.detail, SecurityReports.created_at)\
             .join(Karyawan, SecurityReports.nik == Karyawan.nik)\
             .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
             .filter(SecurityReports.type == 'RADIUS_BYPASS', SecurityReports.status_flag == 'pending')\
             .order_by(SecurityReports.created_at.desc())
    if excluded_niks:
        q_rb = q_rb.filter(SecurityReports.nik.notin_(excluded_niks))
    bypass_requests_raw = q_rb.limit(10).all()
    rb_data = [{
        "id": r.id,
        "nik": r.nik,
        "nama": r.nama_karyawan,
        "cabang": r.nama_cabang,
        "detail": r.detail,
        "type": "RADIUS_BYPASS",
        "time": r.created_at
    } for r in bypass_requests_raw]

    return {
        "mock_locations": mock_data,
        "radius_violations": radius_data,
        "device_locks": device_data,
        "member_expiring": expiring_data,
        "force_closes": fc_data,
        "face_verify_fails": fv_data,
        "fake_gps_alerts": fg_data,
        "radius_bypass_requests": rb_data
    }

class MarkReadRequest(BaseModel):
    id: int

@router.post("/security/notifications/mark-read")
def mark_security_alert_read(
    payload: MarkReadRequest,
    db: Session = Depends(get_db)
):
    report = db.query(SecurityReports).filter(SecurityReports.id == payload.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    report.status_flag = 'read'
    db.commit()
    return {"status": True, "message": "Alert marked as read"}

class ApproveBypassRequest(BaseModel):
    id: int

@router.post("/security/notifications/approve-bypass")
def approve_radius_bypass(
    payload: ApproveBypassRequest,
    db: Session = Depends(get_db)
):
    report = db.query(SecurityReports).filter(SecurityReports.id == payload.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    report.status_flag = 'approved'
    
    # Update Lock Location untuk mengizinkan bypass
    karyawan = db.query(Karyawan).filter(Karyawan.nik == report.nik).first()
    if karyawan:
        karyawan.lock_location = '0'
        
    db.commit()
    return {"status": True, "message": "Izin luar tapak disetujui (1 hari sesi absen)"}

# ==============================================================================
# NEW NOTIFICATION LOGIC (Video Call, FCM Token)
# ==============================================================================

class StartCallRequest(BaseModel):
    room_id: str
    caller_name: str = None

@router.post("/video-call/start")
async def start_video_call(
    payload: StartCallRequest,
    current_user: CurrentUser = Depends(get_current_user_sanctum),
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
            # Query eligible employees (Updated: allow all active status codes like 'K', 'T', '1')
            query = db.query(Karyawan.nik)
            
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

        # 2. Get FCM Tokens - Only latest token per NIK to avoid stale/expired tokens
        from sqlalchemy import func
        # Subquery: get latest updated_at per nik
        latest_subq = db.query(
            KaryawanDevices.nik,
            func.max(KaryawanDevices.updated_at).label('max_updated')
        ).filter(KaryawanDevices.nik.in_(target_niks)).group_by(KaryawanDevices.nik).subquery()
        
        devices = db.query(KaryawanDevices).join(
            latest_subq,
            (KaryawanDevices.nik == latest_subq.c.nik) &
            (KaryawanDevices.updated_at == latest_subq.c.max_updated)
        ).all()
                    
        tokens = [d.fcm_token for d in devices if d.fcm_token]
        # Map token -> device id for cleanup
        token_to_device_id = {d.fcm_token: d.id for d in devices if d.fcm_token}
        
        if not tokens:
             return {"status": False, "message": "No target devices found"}

        # 3. Send FCM Notification (Using Firebase Admin SDK)
        
        actual_caller_name = caller_name
        if not actual_caller_name:
            karyawan = db.query(Karyawan).filter(Karyawan.nik == sender_id).first()
            actual_caller_name = karyawan.nama_karyawan if karyawan else current_user.username

        success_count = 0
        failure_count = 0
        
        # Prepare Message
        # Note: Android high priority is better handled by 'data' payload for background processing
        # but 'android' config can also specific priority.
        
        # Split tokens into chunks of 500 (Multicast limit)
        def chunks(lst, n):
            for i in range(0, len(lst), n):
                yield lst[i:i + n]

        for token_batch in chunks(tokens, 500):
            try:
                msg = messaging.MulticastMessage(
                    data={
                        "type": "video_call_offer",
                        "room": room_id,
                        "caller_name": actual_caller_name,
                        "ttl": "60s"
                    },
                    tokens=token_batch,
                    android=messaging.AndroidConfig(
                        priority='high',
                        ttl=timedelta(seconds=60) # 60 seconds TTL
                    )
                )
                
                response = messaging.send_each_for_multicast(msg)
                success_count += response.success_count
                failure_count += response.failure_count
                
                print(f"🔥 FCM BATCH RESULT: Success={response.success_count}, Failed={response.failure_count}")
                
                if response.failure_count > 0:
                    for idx, resp in enumerate(response.responses):
                        if not resp.success:
                            # Tampilkan Error Detail dari Firebase
                            err = resp.exception
                            token_failed = token_batch[idx]
                            print(f"🔥 FCM ERROR for token {token_failed[:10]}... : {err}")
                            if hasattr(err, 'cause'): print(f"   CAUSE: {err.cause}")
                            if hasattr(err, 'code'): print(f"   CODE: {err.code}")
                            if hasattr(err, 'http_response'): print(f"   HTTP: {err.http_response}")
                            
                            # Auto-delete token invalid (NOT_FOUND) dari DB
                            error_code = getattr(err, 'code', '')
                            if error_code in ('NOT_FOUND', 'registration-token-not-registered', 'INVALID_ARGUMENT'):
                                device_id = token_to_device_id.get(token_failed)
                                if device_id:
                                    print(f"🗑️ Deleting stale token from DB: device_id={device_id}")
                                    stale = db.query(KaryawanDevices).filter(KaryawanDevices.id == device_id).first()
                                    if stale:
                                        db.delete(stale)
                                        db.commit()

            except Exception as e:
                print(f"Error sending batch notification: {e}")
                failure_count += len(token_batch)
                
        return {
            "status": True, 
            "message": f"Call started. Notified {success_count} devices. Failed: {failure_count}",
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

# Create a secondary router to handle /api/android prefix requests from the Android app
router_android = APIRouter(
    prefix="/api/android",
    tags=["Notifications (Android)"],
    responses={404: {"description": "Not found"}},
)

# Re-register the same endpoints on the new router (Function reuse)
router_android.post("/video-call/start")(start_video_call)
router_android.post("/firebase/token")(save_fcm_token)

