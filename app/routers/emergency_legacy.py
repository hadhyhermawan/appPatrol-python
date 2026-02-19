from fastapi import APIRouter, Depends, HTTPException, Body, Form
from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import EmergencyAlerts, SecurityReports, Users, Karyawan
from app.sio import sio as sio_server
from sqlalchemy import desc

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
         # EmergencyAlerts requires NIK column
         raise HTTPException(400, "User tidak memiliki NIK valid utk emergency.")
    
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
    
    # Broadcast Socket (Unified Realtime)
    # Emit to all clients or specific room 'security'
    await sio_server.emit("emergency_broadcast", {
         "id": new_alert.id,
         "type": req.alarm_type,
         "lokasi": req.location,
         "branch": req.branch_code,
         "user": user.username,
         "nik": user.nik,
         "timestamp": str(datetime.now())
    })
    
    return {
        "status": True,
        "message": "Alarm Terkirim",
        "alarm_id": new_alert.id,
        "branch_code": req.branch_code,
        "branch_name": "", # Optional
        "alarm_type": req.alarm_type,
        "retry_after": 0
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
    
    # Example logic: if fail_count > 3, return blocked=True (client side handles logout usually)
    if fail_count and fail_count > 5:
        blocked = True
        message = "Akun terkunci sementara karena aktivitas mencurigakan"

    return {
        "blocked": blocked,
        "message": message
    }
