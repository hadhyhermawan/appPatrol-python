from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.models import HariLibur, Cabang
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

router = APIRouter(
    prefix="/api/settings/hari-libur",
    tags=["Hari Libur"],
    responses={404: {"description": "Not found"}},
)

# DTOs
class HariLiburDTO(BaseModel):
    kode_libur: str
    tanggal: date
    kode_cabang: str
    keterangan: str
    nama_cabang: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CreateHariLiburDTO(BaseModel):
    tanggal: date
    kode_cabang: str
    keterangan: str

class UpdateHariLiburDTO(BaseModel):
    tanggal: date
    kode_cabang: str
    keterangan: str

@router.get("")
async def get_hari_libur_list(
    kode_cabang: Optional[str] = None,
    dari: Optional[date] = None,
    sampai: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(HariLibur, Cabang.nama_cabang)\
        .join(Cabang, HariLibur.kode_cabang == Cabang.kode_cabang)
    
    if kode_cabang:
        query = query.filter(HariLibur.kode_cabang == kode_cabang)
        
    if dari and sampai:
        query = query.filter(HariLibur.tanggal.between(dari, sampai))
        
    results = query.order_by(HariLibur.tanggal.desc()).all()
    
    data = []
    for row in results:
        item = row[0]
        data.append({
            "kode_libur": item.kode_libur,
            "tanggal": item.tanggal.isoformat(),
            "kode_cabang": item.kode_cabang,
            "keterangan": item.keterangan,
            "nama_cabang": row[1],
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None
        })
        
    return data

@router.post("")
async def create_hari_libur(payload: CreateHariLiburDTO, db: Session = Depends(get_db)):
    try:
        # Generate kode_libur: LB + YY + sequential number
        year_suffix = payload.tanggal.strftime('%y')
        prefix = f"LB{year_suffix}"
        
        # Get last code for this year
        last_record = db.query(HariLibur)\
            .filter(HariLibur.kode_libur.like(f"{prefix}%"))\
            .order_by(HariLibur.kode_libur.desc())\
            .first()
        
        if last_record:
            last_num = int(last_record.kode_libur[-3:])
            new_num = last_num + 1
        else:
            new_num = 1
            
        kode_libur = f"{prefix}{new_num:03d}"
        
        new_record = HariLibur(
            kode_libur=kode_libur,
            tanggal=payload.tanggal,
            kode_cabang=payload.kode_cabang,
            keterangan=payload.keterangan,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        
        return {"message": "Data berhasil disimpan", "kode_libur": kode_libur}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{kode_libur}")
async def get_hari_libur_detail(kode_libur: str, db: Session = Depends(get_db)):
    record = db.query(HariLibur, Cabang.nama_cabang)\
        .join(Cabang, HariLibur.kode_cabang == Cabang.kode_cabang)\
        .filter(HariLibur.kode_libur == kode_libur)\
        .first()
        
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    item = record[0]
    return {
        "kode_libur": item.kode_libur,
        "tanggal": item.tanggal.isoformat(),
        "kode_cabang": item.kode_cabang,
        "keterangan": item.keterangan,
        "nama_cabang": record[1]
    }

@router.put("/{kode_libur}")
async def update_hari_libur(kode_libur: str, payload: UpdateHariLiburDTO, db: Session = Depends(get_db)):
    record = db.query(HariLibur).filter(HariLibur.kode_libur == kode_libur).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        record.tanggal = payload.tanggal
        record.kode_cabang = payload.kode_cabang
        record.keterangan = payload.keterangan
        record.updated_at = datetime.now()
        
        db.commit()
        return {"message": "Data berhasil diupdate"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{kode_libur}")
async def delete_hari_libur(kode_libur: str, db: Session = Depends(get_db)):
    record = db.query(HariLibur).filter(HariLibur.kode_libur == kode_libur).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        db.delete(record)
        db.commit()
        return {"message": "Data berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
