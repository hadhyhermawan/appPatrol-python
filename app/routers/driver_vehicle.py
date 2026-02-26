from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from typing import Optional, List
import datetime

from app.database import get_db
from app.models.models import MasterKendaraan

router = APIRouter(prefix="/api/driver/vehicle", tags=["Driver Vehicle (Master Kendaraan)"])

class VehicleDTO(BaseModel):
    nama_kendaraan: str
    plat_nomor: str
    jenis: str
    status: Optional[str] = 'AVAILABLE'
    odometer_terakhir: Optional[int] = 0

class VehicleResponse(VehicleDTO):
    id: int
    created_at: Optional[datetime.datetime]
    updated_at: Optional[datetime.datetime]

    class Config:
        from_attributes = True

@router.get("")
def get_vehicles(
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db)
):
    query = db.query(MasterKendaraan)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                MasterKendaraan.nama_kendaraan.ilike(search_filter),
                MasterKendaraan.plat_nomor.ilike(search_filter)
            )
        )
    
    total_items = query.count()
    total_pages = (total_items + per_page - 1) // per_page
    
    vehicles = query.order_by(MasterKendaraan.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    
    return {
        "status": True,
        "message": "Data Kendaraan",
        "data": vehicles,
        "meta": {
            "current_page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages
        }
    }

@router.get("/{id}")
def get_vehicle(id: int, db: Session = Depends(get_db)):
    vehicle = db.query(MasterKendaraan).filter(MasterKendaraan.id == id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
    return {"status": True, "message": "Detail Kendaraan", "data": vehicle}

@router.post("")
def create_vehicle(data: VehicleDTO, db: Session = Depends(get_db)):
    # Check if plat_nomor exists
    existing = db.query(MasterKendaraan).filter(MasterKendaraan.plat_nomor == data.plat_nomor).first()
    if existing:
        raise HTTPException(status_code=400, detail="Plat Nomor sudah terdaftar")
        
    new_vehicle = MasterKendaraan(
        nama_kendaraan=data.nama_kendaraan,
        plat_nomor=data.plat_nomor,
        jenis=data.jenis,
        status=data.status or 'AVAILABLE',
        odometer_terakhir=data.odometer_terakhir or 0,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now()
    )
    db.add(new_vehicle)
    db.commit()
    db.refresh(new_vehicle)
    return {"status": True, "message": "Kendaraan berhasil ditambahkan", "data": new_vehicle}

@router.put("/{id}")
def update_vehicle(id: int, data: VehicleDTO, db: Session = Depends(get_db)):
    vehicle = db.query(MasterKendaraan).filter(MasterKendaraan.id == id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
        
    # Check if plat_nomor exists for other vehicle
    existing = db.query(MasterKendaraan).filter(MasterKendaraan.plat_nomor == data.plat_nomor, MasterKendaraan.id != id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Plat Nomor sudah terdaftar di kendaraan lain")
        
    vehicle.nama_kendaraan = data.nama_kendaraan
    vehicle.plat_nomor = data.plat_nomor
    vehicle.jenis = data.jenis
    vehicle.status = data.status or 'AVAILABLE'
    vehicle.odometer_terakhir = data.odometer_terakhir if data.odometer_terakhir is not None else vehicle.odometer_terakhir
    vehicle.updated_at = datetime.datetime.now()
    
    db.commit()
    db.refresh(vehicle)
    return {"status": True, "message": "Kendaraan berhasil diupdate", "data": vehicle}

@router.delete("/{id}")
def delete_vehicle(id: int, db: Session = Depends(get_db)):
    vehicle = db.query(MasterKendaraan).filter(MasterKendaraan.id == id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Kendaraan tidak ditemukan")
        
    db.delete(vehicle)
    db.commit()
    return {"status": True, "message": "Kendaraan berhasil dihapus"}
