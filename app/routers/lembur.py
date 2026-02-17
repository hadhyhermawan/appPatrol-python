from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from app.database import get_db
from app.models.models import Lembur, Karyawan, Jabatan, Departemen, Cabang
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

router = APIRouter(
    prefix="/api/lembur",
    tags=["Lembur"],
    responses={404: {"description": "Not found"}},
)

# DTOs
class LemburDTO(BaseModel):
    id: int
    nik: str
    nama_karyawan: Optional[str] = None
    nama_jabatan: Optional[str] = None
    nama_dept: Optional[str] = None
    nama_cabang: Optional[str] = None
    tanggal: date
    lembur_mulai: datetime
    lembur_selesai: datetime
    lembur_in: Optional[datetime] = None
    lembur_out: Optional[datetime] = None
    foto_lembur_in: Optional[str] = None
    foto_lembur_out: Optional[str] = None
    lokasi_lembur_in: Optional[str] = None
    lokasi_lembur_out: Optional[str] = None
    status: str  # 0=pending, 1=approved, 2=rejected
    keterangan: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CreateLemburDTO(BaseModel):
    nik: str
    dari: datetime  # lembur_mulai
    sampai: datetime  # lembur_selesai
    keterangan: str

class UpdateLemburDTO(BaseModel):
    nik: str
    dari: datetime
    sampai: datetime
    keterangan: str
    lembur_in: Optional[datetime] = None
    lembur_out: Optional[datetime] = None

class ApprovalDTO(BaseModel):
    approve: bool  # True for approve, False for reject

@router.get("")
async def get_lembur_list(
    dari: Optional[date] = None,
    sampai: Optional[date] = None,
    nama_karyawan: Optional[str] = None,
    kode_cabang: Optional[str] = None,
    kode_dept: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        Lembur,
        Karyawan.nama_karyawan,
        Jabatan.nama_jabatan,
        Departemen.nama_dept,
        Cabang.nama_cabang
    )\
        .join(Karyawan, Lembur.nik == Karyawan.nik)\
        .join(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
        .join(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
        .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)
    
    if dari and sampai:
        query = query.filter(Lembur.tanggal.between(dari, sampai))
    
    if nama_karyawan:
        query = query.filter(Karyawan.nama_karyawan.like(f'%{nama_karyawan}%'))
        
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
        
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
        
    if status is not None:
        query = query.filter(Lembur.status == status)
        
    results = query.order_by(Lembur.status, desc(Lembur.tanggal)).all()
    
    data = []
    for row in results:
        item = row[0]
        data.append({
            "id": item.id,
            "nik": item.nik,
            "nama_karyawan": row[1],
            "nama_jabatan": row[2],
            "nama_dept": row[3],
            "nama_cabang": row[4],
            "tanggal": item.tanggal.isoformat(),
            "lembur_mulai": item.lembur_mulai.isoformat(),
            "lembur_selesai": item.lembur_selesai.isoformat(),
            "lembur_in": item.lembur_in.isoformat() if item.lembur_in else None,
            "lembur_out": item.lembur_out.isoformat() if item.lembur_out else None,
            "foto_lembur_in": item.foto_lembur_in,
            "foto_lembur_out": item.foto_lembur_out,
            "lokasi_lembur_in": item.lokasi_lembur_in,
            "lokasi_lembur_out": item.lokasi_lembur_out,
            "status": item.status,
            "keterangan": item.keterangan,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None
        })
        
    return data

@router.post("")
async def create_lembur(payload: CreateLemburDTO, db: Session = Depends(get_db)):
    try:
        new_record = Lembur(
            nik=payload.nik,
            tanggal=payload.dari.date(),
            lembur_mulai=payload.dari,
            lembur_selesai=payload.sampai,
            keterangan=payload.keterangan,
            status='0',  # Pending
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        
        return {"message": "Data lembur berhasil disimpan", "id": new_record.id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{id}")
async def get_lembur_detail(id: int, db: Session = Depends(get_db)):
    result = db.query(
        Lembur,
        Karyawan.nama_karyawan,
        Jabatan.nama_jabatan,
        Departemen.nama_dept,
        Cabang.nama_cabang
    )\
        .join(Karyawan, Lembur.nik == Karyawan.nik)\
        .join(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
        .join(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
        .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
        .filter(Lembur.id == id)\
        .first()
        
    if not result:
        raise HTTPException(status_code=404, detail="Data not found")
        
    item = result[0]
    return {
        "id": item.id,
        "nik": item.nik,
        "nama_karyawan": result[1],
        "nama_jabatan": result[2],
        "nama_dept": result[3],
        "nama_cabang": result[4],
        "tanggal": item.tanggal.isoformat(),
        "lembur_mulai": item.lembur_mulai.isoformat(),
        "lembur_selesai": item.lembur_selesai.isoformat(),
        "lembur_in": item.lembur_in.isoformat() if item.lembur_in else None,
        "lembur_out": item.lembur_out.isoformat() if item.lembur_out else None,
        "status": item.status,
        "keterangan": item.keterangan
    }

@router.put("/{id}")
async def update_lembur(id: int, payload: UpdateLemburDTO, db: Session = Depends(get_db)):
    record = db.query(Lembur).filter(Lembur.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        record.nik = payload.nik
        record.tanggal = payload.dari.date()
        record.lembur_mulai = payload.dari
        record.lembur_selesai = payload.sampai
        record.keterangan = payload.keterangan
        
        if payload.lembur_in:
            record.lembur_in = payload.lembur_in
        if payload.lembur_out:
            record.lembur_out = payload.lembur_out
            
        # Update status if both in and out are filled
        if payload.lembur_in and payload.lembur_out:
            record.status = '1'
        
        record.updated_at = datetime.now()
        
        db.commit()
        return {"message": "Data berhasil diupdate"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
async def delete_lembur(id: int, db: Session = Depends(get_db)):
    record = db.query(Lembur).filter(Lembur.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        db.delete(record)
        db.commit()
        return {"message": "Data berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{id}/approve")
async def approve_lembur(id: int, payload: ApprovalDTO, db: Session = Depends(get_db)):
    record = db.query(Lembur).filter(Lembur.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        if payload.approve:
            record.status = '1'  # Approved
            message = "Lembur berhasil disetujui"
        else:
            record.status = '2'  # Rejected
            message = "Lembur ditolak"
            
        record.updated_at = datetime.now()
        db.commit()
        return {"message": message}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{id}/cancel-approve")
async def cancel_approve_lembur(id: int, db: Session = Depends(get_db)):
    record = db.query(Lembur).filter(Lembur.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        record.status = '0'  # Back to pending
        record.updated_at = datetime.now()
        db.commit()
        return {"message": "Approval dibatalkan"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
