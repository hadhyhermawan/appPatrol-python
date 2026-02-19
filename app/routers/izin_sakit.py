from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.models import PresensiIzinsakit, Karyawan, Jabatan, Departemen, Cabang
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from app.core.permissions import get_current_user

router = APIRouter(
    prefix="/api/izin-sakit",
    tags=["Izin Sakit"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

class IzinSakitDTO(BaseModel):
    kode_izin_sakit: str
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
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CreateIzinSakitDTO(BaseModel):
    nik: str
    dari: date
    sampai: date
    keterangan: str

class UpdateIzinSakitDTO(BaseModel):
    nik: str
    dari: date
    sampai: date
    keterangan: str

class ApprovalDTO(BaseModel):
    approve: bool
    keterangan_hrd: Optional[str] = None

@router.get("")
async def get_izin_sakit_list(
    dari: Optional[date] = None,
    sampai: Optional[date] = None,
    nama_karyawan: Optional[str] = None,
    kode_cabang: Optional[str] = None,
    kode_dept: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(
        PresensiIzinsakit,
        Karyawan.nama_karyawan,
        Jabatan.nama_jabatan,
        Departemen.nama_dept,
        Cabang.nama_cabang
    )\
        .join(Karyawan, PresensiIzinsakit.nik == Karyawan.nik)\
        .join(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
        .join(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
        .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)
    
    if dari and sampai:
        query = query.filter(PresensiIzinsakit.tanggal.between(dari, sampai))
    if nama_karyawan:
        query = query.filter(Karyawan.nama_karyawan.like(f'%{nama_karyawan}%'))
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
    if status is not None:
        query = query.filter(PresensiIzinsakit.status == status)
        
    results = query.order_by(PresensiIzinsakit.status, desc(PresensiIzinsakit.tanggal)).all()
    return [{
        "kode_izin_sakit": r[0].kode_izin_sakit, "nik": r[0].nik, "nama_karyawan": r[1],
        "nama_jabatan": r[2], "nama_dept": r[3], "nama_cabang": r[4],
        "tanggal": r[0].tanggal.isoformat(), "dari": r[0].dari.isoformat(),
        "sampai": r[0].sampai.isoformat(), "keterangan": r[0].keterangan,
        "keterangan_hrd": r[0].keterangan_hrd, "foto_bukti": r[0].doc_sid,
        "status": r[0].status,
        "created_at": r[0].created_at.isoformat() if r[0].created_at else None,
        "updated_at": r[0].updated_at.isoformat() if r[0].updated_at else None
    } for r in results]

@router.post("")
async def create_izin_sakit(payload: CreateIzinSakitDTO, db: Session = Depends(get_db)):
    try:
        year_month = payload.dari.strftime('%y%m')
        prefix = f"IS{year_month}"
        last_record = db.query(PresensiIzinsakit).filter(PresensiIzinsakit.kode_izin_sakit.like(f"{prefix}%")).order_by(PresensiIzinsakit.kode_izin_sakit.desc()).first()
        new_num = int(last_record.kode_izin_sakit[-4:]) + 1 if last_record else 1
        kode_izin_sakit = f"{prefix}{new_num:04d}"
        
        new_record = PresensiIzinsakit(
            kode_izin_sakit=kode_izin_sakit, nik=payload.nik, tanggal=payload.dari,
            dari=payload.dari, sampai=payload.sampai, keterangan=payload.keterangan,
            status='0', created_at=datetime.now(), updated_at=datetime.now()
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)
        return {"message": "Data izin sakit berhasil disimpan", "kode_izin_sakit": kode_izin_sakit}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{kode_izin_sakit}")
async def get_izin_sakit_detail(kode_izin_sakit: str, db: Session = Depends(get_db)):
    result = db.query(PresensiIzinsakit, Karyawan.nama_karyawan, Jabatan.nama_jabatan, Departemen.nama_dept, Cabang.nama_cabang)\
        .join(Karyawan, PresensiIzinsakit.nik == Karyawan.nik)\
        .join(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
        .join(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
        .join(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
        .filter(PresensiIzinsakit.kode_izin_sakit == kode_izin_sakit).first()
    if not result:
        raise HTTPException(status_code=404, detail="Data not found")
    return {
        "kode_izin_sakit": result[0].kode_izin_sakit, "nik": result[0].nik, "nama_karyawan": result[1],
        "nama_jabatan": result[2], "nama_dept": result[3], "nama_cabang": result[4],
        "tanggal": result[0].tanggal.isoformat(), "dari": result[0].dari.isoformat(),
        "sampai": result[0].sampai.isoformat(), "keterangan": result[0].keterangan,
        "keterangan_hrd": result[0].keterangan_hrd, "status": result[0].status
    }

@router.put("/{kode_izin_sakit}")
async def update_izin_sakit(kode_izin_sakit: str, payload: UpdateIzinSakitDTO, db: Session = Depends(get_db)):
    record = db.query(PresensiIzinsakit).filter(PresensiIzinsakit.kode_izin_sakit == kode_izin_sakit).first()
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

@router.delete("/{kode_izin_sakit}")
async def delete_izin_sakit(kode_izin_sakit: str, db: Session = Depends(get_db)):
    record = db.query(PresensiIzinsakit).filter(PresensiIzinsakit.kode_izin_sakit == kode_izin_sakit).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
    try:
        db.delete(record)
        db.commit()
        return {"message": "Data berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{kode_izin_sakit}/approve")
async def approve_izin_sakit(kode_izin_sakit: str, payload: ApprovalDTO, db: Session = Depends(get_db)):
    record = db.query(PresensiIzinsakit).filter(PresensiIzinsakit.kode_izin_sakit == kode_izin_sakit).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
    try:
        record.status = '1' if payload.approve else '2'
        if payload.keterangan_hrd:
            record.keterangan_hrd = payload.keterangan_hrd
        record.updated_at = datetime.now()
        db.commit()
        return {"message": "Izin sakit berhasil disetujui" if payload.approve else "Izin sakit ditolak"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{kode_izin_sakit}/cancel-approve")
async def cancel_approve_izin_sakit(kode_izin_sakit: str, db: Session = Depends(get_db)):
    record = db.query(PresensiIzinsakit).filter(PresensiIzinsakit.kode_izin_sakit == kode_izin_sakit).first()
    if not record:
        raise HTTPException(status_code=404, detail="Data not found")
    try:
        record.status = '0'
        record.updated_at = datetime.now()
        db.commit()
        return {"message": "Approval dibatalkan"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
