from fastapi import APIRouter, Depends, HTTPException, Body, Form
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import EmployeeLocations, EmployeeLocationHistories, EmployeeStatus, Karyawan, Cabang, KaryawanDevices

import firebase_admin
from firebase_admin import credentials, messaging
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("/var/www/appPatrol-python/serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
except Exception as e:
    pass

router = APIRouter(
    prefix="/api/android",
    tags=["Tracking Legacy"],
)

@router.post("/tracking/location")
async def update_location(
    latitude: float = Form(...),
    longitude: float = Form(...),
    accuracy: float = Form(None),
    speed: float = Form(None),
    bearing: float = Form(None),
    provider: str = Form("gps"),
    isMocked: int = Form(0),
    batteryLevel: int = Form(0),
    isCharging: int = Form(0),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    if not user.nik:
        raise HTTPException(400, "User NIK required")
        
    # Update Current Location
    loc = db.query(EmployeeLocations).filter(EmployeeLocations.nik == user.nik).first()
    if not loc:
        loc = EmployeeLocations(nik=user.nik, id=user.id) # user.id is optional but good to link
        db.add(loc)
    
    loc.latitude = latitude
    loc.longitude = longitude
    loc.accuracy = accuracy
    loc.speed = speed
    loc.bearing = bearing
    loc.provider = provider
    loc.is_mocked = isMocked
    loc.updated_at = datetime.now()
    
    # Add History
    history = EmployeeLocationHistories(
        nik=user.nik,
        user_id=user.id,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        speed=speed,
        bearing=bearing,
        provider=provider,
        is_mocked=isMocked,
        recorded_at=datetime.now()
    )
    db.add(history)
    
    # Update Status as well (Battery)
    status = db.query(EmployeeStatus).filter(EmployeeStatus.nik == user.nik).first()
    if not status:
        status = EmployeeStatus(nik=user.nik, user_id=user.id)
        db.add(status)
        
    status.battery_level = batteryLevel
    status.is_charging = isCharging
    status.last_seen = datetime.now()
    status.is_online = 1 # Assume online if sending location
    
    db.commit()

    # --- ENTERPRISE OPTIMIZATION: REAL-TIME MOCK LOCATION ALERT ---
    if isMocked == 1:
        try:
            # Cegah spam alert: cek apakah dalam 1 jam terakhir sudah pernah dikirim alarm 
            # Fake GPS untuk NIK ini. Jika sudah, skip agar HP Komandan tidak berisik.
            from datetime import timedelta
            satu_jam_lalu = datetime.now() - timedelta(hours=1)
            
            # Kita bisa cek dari tabel security_reports 
            from app.models.models import SecurityReports
            recent_mock_alert = db.query(SecurityReports).filter(
                SecurityReports.nik == user.nik,
                SecurityReports.type == 'FAKE_GPS',
                SecurityReports.created_at >= satu_jam_lalu
            ).first()
            
            if not recent_mock_alert:
                karyawan_pelanggar = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
                if karyawan_pelanggar and karyawan_pelanggar.kode_cabang:
                    target_karyawans = db.query(Karyawan.nik).filter(
                        Karyawan.kode_cabang == karyawan_pelanggar.kode_cabang,
                        Karyawan.nik != user.nik
                    ).all()
                    
                    target_niks = [r[0] for r in target_karyawans]
                    if target_niks:
                        devices = db.query(KaryawanDevices).filter(KaryawanDevices.nik.in_(target_niks)).all()
                        tokens = [d.fcm_token for d in devices if d.fcm_token]
                        
                        if tokens:
                            nama_pelanggar = karyawan_pelanggar.nama_karyawan or user.nik
                            cabang_info = db.query(Cabang).filter(Cabang.kode_cabang == karyawan_pelanggar.kode_cabang).first()
                            nama_cabang = cabang_info.nama_cabang if cabang_info else "Cabang"

                            alert_title = "⚠️ INDIKASI FAKE GPS"
                            alert_body = f"Personel {nama_pelanggar} terdeteksi menggunakan aplikasi Titik Lokasi Palsu (Fake GPS) di area {nama_cabang}."
                            
                            msg = messaging.MulticastMessage(
                                notification=messaging.Notification(
                                    title=alert_title,
                                    body=alert_body
                                ),
                                data={
                                    "type": "SECURITY_ALERT",
                                    "subtype": "FAKE_GPS",
                                    "nik_pelanggar": user.nik,
                                    "nama_pelanggar": nama_pelanggar
                                },
                                tokens=tokens[:500],
                                android=messaging.AndroidConfig(priority='high')
                            )
                            messaging.send_each_for_multicast(msg)
                            print(f"MOCK LOCATION ESCALATION SENT for NIK: {user.nik}")

                # Catat ke security_reports agar dicentang sudah diingatkan
                report = SecurityReports(
                    type='FAKE_GPS',
                    detail=f"Terdeteksi otomatis melalui modul Tracking Android. Coordinate: {latitude},{longitude}",
                    user_id=user.id,
                    nik=user.nik,
                    latitude=latitude,
                    longitude=longitude,
                    status_flag='pending',
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(report)
                db.commit()

        except Exception as alert_err:
            print(f"Failed to push escalate Mock Location concern: {alert_err}")
            
    # --- ESCALATION: OUT OF LOCATION WHILE ACTIVE SESSIONS ---
    try:
        from app.models.models import Presensi
        from datetime import date
        today_date = date.today()
        # Check if user has active shift (jam_in exist but jam_out is NULL)
        active_session = db.query(Presensi).filter(
            Presensi.nik == user.nik, 
            Presensi.tanggal == today_date,
            Presensi.jam_in != None,
            Presensi.jam_out == None
        ).first()

        if active_session:
            karyawan_pelanggar = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
            if karyawan_pelanggar and karyawan_pelanggar.lock_location == '1':
                cabang_info = db.query(Cabang).filter(Cabang.kode_cabang == karyawan_pelanggar.kode_cabang).first()
                if cabang_info and cabang_info.lokasi_cabang and cabang_info.radius_cabang > 0:
                    import math
                    clat, clon = map(float, cabang_info.lokasi_cabang.split(','))
                    dLat = math.radians(clat - latitude)
                    dLon = math.radians(clon - longitude)
                    a = math.sin(dLat/2) * math.sin(dLat/2) + \
                        math.cos(math.radians(latitude)) * math.cos(math.radians(clat)) * \
                        math.sin(dLon/2) * math.sin(dLon/2)
                    c_val = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                    dist = 6371000 * c_val
                    
                    if dist > cabang_info.radius_cabang:
                        # User is OUT OF LOCATION while ACTIVE!
                        from datetime import timedelta
                        satu_jam_lalu = datetime.now() - timedelta(hours=1)
                        from app.models.models import SecurityReports
                        recent_out_alert = db.query(SecurityReports).filter(
                            SecurityReports.nik == user.nik,
                            SecurityReports.type == 'OUT_OF_LOCATION',
                            SecurityReports.created_at >= satu_jam_lalu
                        ).first()

                        if not recent_out_alert:
                            target_karyawans = db.query(Karyawan.nik).filter(
                                Karyawan.kode_cabang == karyawan_pelanggar.kode_cabang,
                                Karyawan.nik != user.nik
                            ).all()
                            
                            target_niks = [r[0] for r in target_karyawans]
                            if target_niks:
                                devices = db.query(KaryawanDevices).filter(KaryawanDevices.nik.in_(target_niks)).all()
                                tokens = [d.fcm_token for d in devices if d.fcm_token]
                                
                                if tokens:
                                    nama_pelanggar = karyawan_pelanggar.nama_karyawan or user.nik
                                    nama_cabang = cabang_info.nama_cabang if cabang_info else "Cabang"

                                    alert_title = "⚠️ ANGGOTA KELUAR RADIUS"
                                    alert_body = f"Personel {nama_pelanggar} terdeteksi berada di luar jangkauan area {nama_cabang} saat jam bertugas."
                                    
                                    msg = messaging.MulticastMessage(
                                        notification=messaging.Notification(
                                            title=alert_title,
                                            body=alert_body
                                        ),
                                        data={
                                            "type": "SECURITY_ALERT",
                                            "subtype": "OUT_OF_LOCATION",
                                            "nik_pelanggar": user.nik,
                                            "nama_pelanggar": nama_pelanggar
                                        },
                                        tokens=tokens[:500],
                                        android=messaging.AndroidConfig(priority='high')
                                    )
                                    messaging.send_each_for_multicast(msg)
                                    print(f"OUT OF LOCATION ESCALATION SENT for NIK: {user.nik}")

                            # Catat ke security_reports
                            report = SecurityReports(
                                type='OUT_OF_LOCATION',
                                detail=f"Terdeteksi otomatis melalui modul Live Tracking. Jarak: {int(dist)}m dari maksimal {int(cabang_info.radius_cabang)}m",
                                user_id=user.id,
                                nik=user.nik,
                                latitude=latitude,
                                longitude=longitude,
                                status_flag='pending',
                                created_at=datetime.now(),
                                updated_at=datetime.now()
                            )
                            db.add(report)
                            db.commit()
    except Exception as err:
        print(f"Failed handling OUT_OF_LOCATION live stream concern: {err}")
    # ----------------------------------------------------------------
    
    return {"status": True, "message": "Location Updated"}

@router.post("/tracking/status")
async def update_status(
    isOnline: int = Form(None),
    batteryLevel: int = Form(None),
    isCharging: int = Form(None),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    if not user.nik:
         raise HTTPException(400, "NIK Required")
         
    status = db.query(EmployeeStatus).filter(EmployeeStatus.nik == user.nik).first()
    if not status:
        status = EmployeeStatus(nik=user.nik, user_id=user.id)
        db.add(status)
    
    if isOnline is not None:
        status.is_online = isOnline
    if batteryLevel is not None:
        status.battery_level = batteryLevel
    if isCharging is not None:
        status.is_charging = isCharging
        
    status.updated_at = datetime.now()
    status.last_seen = datetime.now()
    
    db.commit()
    return {"status": True, "message": "Status Updated"}

@router.get("/tracking/employee/{nik}")
async def get_employee_tracking(
    nik: str,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # Get Employee Info + Latest Location + Status
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if not karyawan:
        raise HTTPException(404, "Employee Not Found")
        
    loc = db.query(EmployeeLocations).filter(EmployeeLocations.nik == nik).first()
    status = db.query(EmployeeStatus).filter(EmployeeStatus.nik == nik).first()
    
    data = {
        "nik": karyawan.nik,
        "nama": karyawan.nama_karyawan,
        "latitude": float(loc.latitude) if loc else None,
        "longitude": float(loc.longitude) if loc else None,
        "updated_at": str(loc.updated_at) if loc else None,
        "is_online": status.is_online if status else 0,
        "battery_level": status.battery_level if status else 0,
        "is_charging": status.is_charging if status else 0,
        "last_seen": str(status.last_seen) if status else None
    }
    
    return {"status": True, "data": data}
