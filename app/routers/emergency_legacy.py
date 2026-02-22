from fastapi import APIRouter, Depends, HTTPException, Body, Form
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import EmergencyAlerts, SecurityReports, Users, Karyawan, Cabang, KaryawanDevices
from app.sio import sio as sio_server
from sqlalchemy import desc
import firebase_admin
from firebase_admin import credentials, messaging

# Initialize Firebase if not already initialized
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("/var/www/appPatrol-python/serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
except Exception as e:
    pass

router = APIRouter(
    prefix="/api/android",
    tags=["Emergency Legacy"],
)

class EmergencyTriggerReq(BaseModel):
    branch_code: Optional[str] = None
    user_id: Optional[int] = None
    timestamp: Optional[str] = None
    location: Optional[str] = None
    alarm_type: str

@router.post("/emergency/trigger")
async def trigger_emergency(
    req: EmergencyTriggerReq,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    if not user.nik:
        raise HTTPException(400, "User tidak memiliki NIK valid untuk emergency.")

    # 1. Cek absen masuk aktif (konsisten dengan fitur operasional lainnya)
    from datetime import date, timedelta
    from app.models.models import Presensi
    today = date.today()
    yesterday = today - timedelta(days=1)

    presensi_aktif = db.query(Presensi).filter(
        Presensi.nik == user.nik,
        Presensi.tanggal == today,
        Presensi.jam_in != None,
        Presensi.jam_out == None
    ).first()

    if not presensi_aktif:
        # Cek lintas hari
        presensi_aktif = db.query(Presensi).filter(
            Presensi.nik == user.nik,
            Presensi.tanggal == yesterday,
            Presensi.lintashari == 1,
            Presensi.jam_in != None,
            Presensi.jam_out == None
        ).first()

    if not presensi_aktif:
        raise HTTPException(status_code=403, detail="Anda belum absen masuk atau sudah absen pulang.")

    # 2. Cooldown: cegah spam trigger (60 detik)
    cooldown_seconds = 60
    recent = db.query(EmergencyAlerts).filter(
        EmergencyAlerts.nik == user.nik
    ).order_by(desc(EmergencyAlerts.triggered_at)).first()

    if recent and recent.triggered_at:
        elapsed = (datetime.now() - recent.triggered_at).total_seconds()
        if elapsed < cooldown_seconds:
            retry_after = int(cooldown_seconds - elapsed)
            return {
                "status": False,
                "message": f"Harap tunggu {retry_after} detik sebelum mengirim alarm lagi.",
                "retry_after": retry_after
            }

    # 3. Ambil nama cabang dari karyawan
    karyawan = db.query(Karyawan).filter(Karyawan.nik == user.nik).first()
    branch_name = ""
    if karyawan:
        from app.models.models import Cabang
        cabang = db.query(Cabang).filter(Cabang.kode_cabang == req.branch_code).first()
        branch_name = cabang.nama_cabang if cabang and hasattr(cabang, 'nama_cabang') else (karyawan.nama_cabang if hasattr(karyawan, 'nama_cabang') else "")

    new_alert = EmergencyAlerts(
        id_user=user.id,
        nik=user.nik,
        alarm_type=req.alarm_type,
        response_status='pending',
        branch_code=req.branch_code,
        location=req.location,
        triggered_at=datetime.now(),
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)

    # Broadcast Socket
    await sio_server.emit("emergency_broadcast", {
        "id": new_alert.id,
        "type": req.alarm_type,
        "lokasi": req.location,
        "branch": req.branch_code,
        "branch_name": branch_name,
        "user": user.username,
        "nik": user.nik,
        "timestamp": str(datetime.now())
    })

    # Broadcast FCM Push Notification (Antar Cabang / Cross Branch)
    try:
        devices = db.query(KaryawanDevices).filter(KaryawanDevices.fcm_token != None).all()
        tokens = list(set([d.fcm_token for d in devices if d.fcm_token]))
        
        if tokens:
            nama_pelapor = karyawan.nama_karyawan if karyawan and karyawan.nama_karyawan else user.username
            
            msg = messaging.MulticastMessage(
                data={
                    "type": "emergency",
                    "alarm_id": str(new_alert.id),
                    "alarm_type": req.alarm_type,
                    "branch_code": req.branch_code or "",
                    "branch_name": branch_name or "Pusat",
                    "title": "🚨 ALARM DARURAT 🚨",
                    "body": f"SOS ditekan oleh {nama_pelapor} di {branch_name or 'lokasi tidak diketahui'}!",
                },
                tokens=tokens[:500],
                android=messaging.AndroidConfig(priority='high')
            )
            response = messaging.send_each_for_multicast(msg)
            print(f"SOS FCM SENT. Success: {response.success_count}, Failed: {response.failure_count}")
    except Exception as e:
        print(f"Failed to send SOS FCM: {e}")

    return {
        "status": True,
        "message": "Alarm darurat berhasil dikirim!",
        "alarm_id": new_alert.id,
        "branch_code": req.branch_code,
        "branch_name": branch_name,
        "alarm_type": req.alarm_type,
        "retry_after": cooldown_seconds
    }


@router.get("/emergency/logs")
async def get_emergency_logs(
    branch_code: Optional[str] = None,
    alarm_type: Optional[str] = None,
    user_id: Optional[int] = None,
    date_filter: Optional[str] = None, # 'date' param name conflicts with python type
    limit: int = 10,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # Base query
    query = db.query(EmergencyAlerts)
    
    if branch_code:
        query = query.filter(EmergencyAlerts.branch_code == branch_code)
        
    if user_id:
        query = query.filter(EmergencyAlerts.id_user == user_id)
        
    # Order by triggered_at desc
    logs = query.order_by(desc(EmergencyAlerts.triggered_at)).limit(limit).all()
    
    items = []
    for log in logs:
        # Fetch sender name/nik if relation loaded or lazy load
        # For simplicity return basic fields
        items.append({
            "id": log.id,
            "id_user": log.id_user,
            "nik": log.nik,
            "branch_code": log.branch_code,
            "alarm_type": log.alarm_type,
            "location": log.location,
            "response_status": log.response_status,
            "created_at": str(log.triggered_at)
        })
        
    return {
        "status": True,
        "data": {
            "current_page": 1,
            "data": items,
            "per_page": limit,
            "total": len(items)
        }
    }

@router.post("/security/report-abuse")
async def report_abuse(
    type: str = Form(...),
    detail: str = Form(""),
    lokasi: str = Form(None),
    fail_count: int = Form(0),
    device_model: str = Form(None),
    device_id: str = Form(None),
    lat: float = Form(None),
    lon: float = Form(None),
    nik: str = Form(None), # Android params
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    used_nik = user.nik if user.nik else nik
    
    report = SecurityReports(
        type=type,
        detail=detail,
        user_id=user.id,
        nik=used_nik,
        latitude=lat,
        longitude=lon,
        device_model=device_model,
        device_id=device_id,
        fail_count=fail_count,
        status_flag='pending',
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    db.add(report)
    db.commit()
    
    # Logic Blocking?
    blocked = False
    message = "Laporan diterima"
    
    # Trigger escalation criteria
    needs_escalation = False
    alert_title = "🚨 PERINGATAN KEAMANAN"
    alert_body = ""

    if fail_count and fail_count > 5:
        blocked = True
        needs_escalation = True
        message = "Akun terkunci sementara karena aktivitas mencurigakan"
        alert_body = "Perangkat/Akun Personel {nama} dikunci oleh sistem akibat gagal verifikasi wajah berturut-turut di Area {cabang}."

    elif type == 'APP_FORCE_CLOSE':
        # Don't block, but notify supervisor
        blocked = False
        needs_escalation = True
        message = "Peringatan: Sistem mendeteksi bahwa aplikasi dipaksa berhenti atau ditutup tidak wajar."
        alert_title = "⚠️ INDIKASI FORCE CLOSE APLIKASI"
        alert_body = "Personel {nama} terdeteksi menutup paksa aplikasi K3Guard dari Recent Apps / Pemaksaan Berhenti di Area {cabang}."

    if needs_escalation:
        # --- ENTERPRISE OPTIMIZATION: ESCALATION PUSH NOTIFICATION ---
        try:
            karyawan = db.query(Karyawan).filter(Karyawan.nik == used_nik).first()
            if karyawan and karyawan.kode_cabang:
                target_karyawans = db.query(Karyawan.nik).filter(
                     Karyawan.kode_cabang == karyawan.kode_cabang,
                     Karyawan.nik != used_nik
                ).all()
                target_niks = [r[0] for r in target_karyawans]
                
                if target_niks:
                    devices = db.query(KaryawanDevices).filter(KaryawanDevices.nik.in_(target_niks)).all()
                    tokens = [d.fcm_token for d in devices if d.fcm_token]
                    
                    if tokens:
                        nama_pelanggar = karyawan.nama_karyawan or used_nik
                        cabang_info = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
                        nama_cabang = cabang_info.nama_cabang if cabang_info else "Cabang"

                        msg = messaging.MulticastMessage(
                            notification=messaging.Notification(
                                title=alert_title,
                                body=alert_body.format(nama=nama_pelanggar, cabang=nama_cabang)
                            ),
                            data={
                                "type": "SECURITY_ALERT",
                                "subtype": type,
                                "nik_pelanggar": used_nik,
                                "nama_pelanggar": nama_pelanggar
                            },
                            tokens=tokens[:500], # Max 500 per batch
                            android=messaging.AndroidConfig(priority='high')
                        )
                        
                        response = messaging.send_each_for_multicast(msg)
                        print(f"SECURITY ESCALATION SENT. Success: {response.success_count}, Failed: {response.failure_count}")

        except Exception as push_err:
            print(f"Failed to push escalate security concern: {push_err}")
        # -------------------------------------------------------------

    return {
        "blocked": blocked,
        "message": message
    }
