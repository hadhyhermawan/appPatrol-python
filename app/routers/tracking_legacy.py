from fastapi import APIRouter, Depends, HTTPException, Body, Form
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import EmployeeLocations, EmployeeLocationHistories, EmployeeStatus, Karyawan

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
