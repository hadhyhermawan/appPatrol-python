from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.models import PresensiIzinabsen, Karyawan, Jabatan, Departemen, Cabang
from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

router = APIRouter(
    prefix="/api/izin",
    tags=["Izin Absen"],
    responses={404: {"description": "Not found"}},
)

# DTOs
class IzinAbsenDTO(BaseModel):
    kode_izin: str
    nik: str
    nama_karyawan: Optional[str] = None
    nama_jabatan: Optional[str] = None
    nama_dept: Optional[str] = None
    nama_cabang: Optional[str] = None
    tanggal: date
    dari: date
    sampai: date
    keterangan: str
    keterangan_hrd: Optional[str] = None
    foto_bukti: Optional[str] = None
    status: str  # '0'=pending, '1'=approved, '2'=rejected
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CreateIzinAbsenDTO(BaseModel):
    nik: str
    dari: date
    sampai: date
    keterangan: str

class UpdateIzinAbsenDTO(BaseModel):
    nik: str
    dari: date
    sampai: date
    keterangan: str

class ApprovalDTO(BaseModel):
    approve: bool  # True for approve, False for reject
    keterangan_hrd: Optional[str] = None

@router.get("")
async def get_izin_absen_list(
    dari: Optional[date] = None,
    sampai: Optional[date] = None,
    nama_karyawan: Optional[str] = None,
    kode_cabang: Optional[str] = None,
    kode_dept: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        PresensiIzinabsen,
        Karyawan.nama_karyawan,
        Jabatan.nama_jabatan,
        Departemen.nama_dept,
        Cabang.nama_cabang
    )\
        .join(Karyawan, PresensiIzinabsen.nik == Karyawan.nik)\
        .join(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
        .join(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
        .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)
    
    if dari and sampai:
        query = query.filter(PresensiIzinabsen.tanggal.between(dari, sampai))
    
    if nama_karyawan:
        query = query.filter(Karyawan.nama_karyawan.like(f'%{nama_karyawan}%'))
        
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
        
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
        
    if status is not None:
        query = query.filter(PresensiIzinabsen.status == status)
        
    results = query.order_by(PresensiIzinabsen.status, desc(PresensiIzinabsen.tanggal)).all()
    
    data = []
    for row in results:
        item = row[0]
        data.append({
            "kode_izin": item.kode_izin,
            "nik": item.nik,
            "nama_karyawan": row[1],
            "nama_jabatan": row[2],
            "nama_dept": row[3],
            "nama_cabang": row[4],
            "tanggal": item.tanggal.isoformat(),
            "dari": item.dari.isoformat(),
            "sampai": item.sampai.isoformat(),
            "keterangan": item.keterangan,
            "keterangan_hrd": item.keterangan_hrd,
            "foto_bukti": item.foto_bukti,
            "status": item.status,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None
        })
        
    return data

@router.post("")
async def create_izin_absen(payload: CreateIzinAbsenDTO, db: Session = Depends(get_db)):
    try:
        # Generate kode_izin: IA{YYMM}{sequence}
        year_month = payload.dari.strftime('%y%m')
        prefix = f"IA{year_month}"
        
        # Get last code for this month
        last_record = db.query(PresensiIzinabsen)\
            .filter(PresensiIzinabsen.kode_izin.like(f"{prefix}%"))\
            .order_by(PresensiIzinabsen.kode_izin.desc())\
            .first()
        
        if last_record:
            last_num = int(last_record.kode_izin[-4:])
            new_num = last_num + 1
        else:
            new_num = 1
            
        kode_izin = f"{prefix}{new_num:04d}"
        
        new_record = PresensiIzinabsen(
            kode_izin=kode_izin,
            nik=payload.nik,
            tanggal=payload.dari,
            dari=payload.dari,
            sampai=payload.sampai,
            keterangan=payload.keterangan,
            status='0',  # Pending
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        
        return {"message": "Data izin berhasil disimpan", "kode_izin": kode_izin}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{kode_izin}")
async def get_izin_absen_detail(kode_izin: str, db: Session = Depends(get_db)):
    result = db.query(
        PresensiIzinabsen,
        Karyawan.nama_karyawan,
        Jabatan.nama_jabatan,
        Departemen.nama_dept,
        Cabang.nama_cabang
    )\
        .join(Karyawan, PresensiIzinabsen.nik == Karyawan.nik)\
        .join(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
        .join(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
        .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
        .filter(PresensiIzinabsen.kode_izin == kode_izin)\
        .first()
        
    if not result:
        raise HTTPException(status_code=404, detail="Data not found")
        
    item = result[0]
    return {
        "kode_izin": item.kode_izin,
        "nik": item.nik,
        "nama_karyawan": result[1],
        "nama_jabatan": result[2],
        "nama_dept": result[3],
        "nama_cabang": result[4],
        "tanggal": item.tanggal.isoformat(),
        "dari": item.dari.isoformat(),
        "sampai": item.sampai.isoformat(),
        "keterangan": item.keterangan,
        "keterangan_hrd": item.keterangan_hrd,
        "status": item.status
    }

@router.put("/{kode_izin}")
async def update_izin_absen(kode_izin: str, payload: UpdateIzinAbsenDTO, db: Session = Depends(get_db)):
    record = db.query(PresensiIzinabsen).filter(PresensiIzinabsen.kode_izin == kode_izin).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        record.nik = payload.nik
        record.tanggal = payload.dari
        record.dari = payload.dari
        record.sampai = payload.sampai
        record.keterangan = payload.keterangan
        record.updated_at = datetime.now()
        
        db.commit()
        return {"message": "Data berhasil diupdate"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{kode_izin}")
async def delete_izin_absen(kode_izin: str, db: Session = Depends(get_db)):
    record = db.query(PresensiIzinabsen).filter(PresensiIzinabsen.kode_izin == kode_izin).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        db.delete(record)
        db.commit()
        return {"message": "Data berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{kode_izin}/approve")
async def approve_izin_absen(kode_izin: str, payload: ApprovalDTO, db: Session = Depends(get_db)):
    record = db.query(PresensiIzinabsen).filter(PresensiIzinabsen.kode_izin == kode_izin).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        if payload.approve:
            record.status = '1'  # Approved
            message = "Izin absen berhasil disetujui"
        else:
            record.status = '2'  # Rejected
            message = "Izin absen ditolak"
        
        if payload.keterangan_hrd:
            record.keterangan_hrd = payload.keterangan_hrd
            
        record.updated_at = datetime.now()
        db.commit()
        return {"message": message}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{kode_izin}/cancel-approve")
async def cancel_approve_izin_absen(kode_izin: str, db: Session = Depends(get_db)):
    record = db.query(PresensiIzinabsen).filter(PresensiIzinabsen.kode_izin == kode_izin).first()
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
