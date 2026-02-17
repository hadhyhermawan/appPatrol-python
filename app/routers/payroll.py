from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.models import JenisTunjangan, KaryawanGajiPokok, Karyawan, KaryawanTunjangan, KaryawanTunjanganDetail, KaryawanBpjsKesehatan, KaryawanBpjstenagakerja, KaryawanPenyesuaianGaji, KaryawanPenyesuaianGajiDetail, SlipGaji
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date
from fastapi import Query
from sqlalchemy import func

router = APIRouter(
    prefix="/api/payroll",
    tags=["Payroll"]
)

class JenistunjanganDTO(BaseModel):
    kode_jenis_tunjangan: str
    jenis_tunjangan: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.get("/jenis-tunjangan", response_model=List[JenistunjanganDTO])
async def get_jenis_tunjangan(db: Session = Depends(get_db)):
    return db.query(JenisTunjangan).all()

class EmployeeOption(BaseModel):
    nik: str
    nama_karyawan: str
    
@router.get("/employees-list", response_model=List[EmployeeOption])
async def get_employees_list(db: Session = Depends(get_db)):
    karyawan = db.query(Karyawan).order_by(Karyawan.nama_karyawan).all()
    return [{"nik": k.nik, "nama_karyawan": k.nama_karyawan} for k in karyawan]

class CreateJenistunjanganDTO(BaseModel):
    kode_jenis_tunjangan: str
    jenis_tunjangan: str

@router.post("/jenis-tunjangan", response_model=JenistunjanganDTO)
async def create_jenis_tunjangan(
    payload: CreateJenistunjanganDTO,
    db: Session = Depends(get_db)
):
    try:
        exists = db.query(JenisTunjangan).filter(JenisTunjangan.kode_jenis_tunjangan == payload.kode_jenis_tunjangan).first()
        if exists:
            raise HTTPException(status_code=400, detail="Kode Jenis Tunjangan already exists")
            
        new_item = JenisTunjangan(
            kode_jenis_tunjangan=payload.kode_jenis_tunjangan,
            jenis_tunjangan=payload.jenis_tunjangan,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/jenis-tunjangan/{kode}", response_model=JenistunjanganDTO)
async def update_jenis_tunjangan(
    kode: str,
    payload: CreateJenistunjanganDTO,
    db: Session = Depends(get_db)
):
    try:
        item = db.query(JenisTunjangan).filter(JenisTunjangan.kode_jenis_tunjangan == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="Jenis Tunjangan not found")
        
        # Check if new code exists if changed
        if payload.kode_jenis_tunjangan != kode:
             exists = db.query(JenisTunjangan).filter(JenisTunjangan.kode_jenis_tunjangan == payload.kode_jenis_tunjangan).first()
             if exists:
                raise HTTPException(status_code=400, detail="New Kode Jenis Tunjangan already exists")
        
        item.kode_jenis_tunjangan = payload.kode_jenis_tunjangan
        item.jenis_tunjangan = payload.jenis_tunjangan
        item.updated_at = datetime.now()
        
        db.commit()
        db.refresh(item)
        return item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/jenis-tunjangan/{kode}")
async def delete_jenis_tunjangan(kode: str, db: Session = Depends(get_db)):
    try:
        item = db.query(JenisTunjangan).filter(JenisTunjangan.kode_jenis_tunjangan == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="Jenis Tunjangan not found")
        
        db.delete(item)
        db.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# GAJI POKOK
# ==========================================

class CreateGajiPokokDTO(BaseModel):
    nik: str
    jumlah: int
    tanggal_berlaku: date

class UpdateGajiPokokDTO(BaseModel):
    jumlah: int
    tanggal_berlaku: date

class GajiPokokDTO(BaseModel):
    kode_gaji: str
    nik: str
    nama_karyawan: Optional[str] = None
    kode_dept: Optional[str] = None
    kode_cabang: Optional[str] = None
    jumlah: int
    tanggal_berlaku: date
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.get("/gaji-pokok", response_model=List[GajiPokokDTO])
async def get_gaji_pokok(
    keyword: Optional[str] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    limit: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(KaryawanGajiPokok).join(Karyawan, KaryawanGajiPokok.nik == Karyawan.nik)
    
    if keyword:
        query = query.filter(Karyawan.nama_karyawan.like(f"%{keyword}%"))
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
        
    data = query.order_by(desc(KaryawanGajiPokok.created_at)).limit(limit).all()
    
    result = []
    for item in data:
        dto = GajiPokokDTO.model_validate(item)
        dto.nama_karyawan = item.karyawan.nama_karyawan if item.karyawan else None
        dto.kode_dept = item.karyawan.kode_dept if item.karyawan else None
        dto.kode_cabang = item.karyawan.kode_cabang if item.karyawan else None
        result.append(dto)
        
    return result

@router.post("/gaji-pokok", response_model=GajiPokokDTO)
async def create_gaji_pokok(payload: CreateGajiPokokDTO, db: Session = Depends(get_db)):
    try:
        # Code Generation Logic: G + YY + XXXX (4 digit sequence)
        year_suffix = payload.tanggal_berlaku.strftime('%y') # YY
        prefix = f"G{year_suffix}"
        
        # Find last code with this prefix
        last = db.query(KaryawanGajiPokok)\
            .filter(KaryawanGajiPokok.kode_gaji.like(f"{prefix}%"))\
            .order_by(desc(KaryawanGajiPokok.kode_gaji))\
            .first()
            
        if last:
            # Extract sequence number 
            try:
                last_seq = int(last.kode_gaji[3:]) 
                new_seq = last_seq + 1
            except ValueError:
                new_seq = 1
        else:
            new_seq = 1
            
        new_code = f"{prefix}{str(new_seq).zfill(4)}"
        
        new_item = KaryawanGajiPokok(
            kode_gaji=new_code,
            nik=payload.nik,
            jumlah=payload.jumlah,
            tanggal_berlaku=payload.tanggal_berlaku,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        
        # Fetch related karyawan info for response
        dto = GajiPokokDTO.model_validate(new_item)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == payload.nik).first()
        if karyawan:
            dto.nama_karyawan = karyawan.nama_karyawan
            dto.kode_dept = karyawan.kode_dept
            dto.kode_cabang = karyawan.kode_cabang
            
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/gaji-pokok/{kode}", response_model=GajiPokokDTO)
async def update_gaji_pokok(kode: str, payload: UpdateGajiPokokDTO, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanGajiPokok).filter(KaryawanGajiPokok.kode_gaji == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="Gaji Pokok not found")
            
        item.jumlah = payload.jumlah
        item.tanggal_berlaku = payload.tanggal_berlaku
        item.updated_at = datetime.now()
        
        db.commit()
        db.refresh(item)
        
        dto = GajiPokokDTO.model_validate(item)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == item.nik).first()
        if karyawan:
            dto.nama_karyawan = karyawan.nama_karyawan
            dto.kode_dept = karyawan.kode_dept
            dto.kode_cabang = karyawan.kode_cabang
            
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/gaji-pokok/{kode}")
async def delete_gaji_pokok(kode: str, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanGajiPokok).filter(KaryawanGajiPokok.kode_gaji == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="Gaji Pokok not found")
            
        db.delete(item)
        db.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# TUNJANGAN
# ==========================================

class TunjanganDetailDTO(BaseModel):
    kode_jenis_tunjangan: str
    jenis_tunjangan_nama: Optional[str] = None
    jumlah: int

class CreateTunjanganDTO(BaseModel):
    nik: str
    tanggal_berlaku: date
    details: List[TunjanganDetailDTO]

class UpdateTunjanganDTO(BaseModel):
    tanggal_berlaku: date
    details: List[TunjanganDetailDTO]

class TunjanganDTO(BaseModel):
    kode_tunjangan: str
    nik: str
    nama_karyawan: Optional[str] = None
    kode_dept: Optional[str] = None
    kode_cabang: Optional[str] = None
    tanggal_berlaku: date
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    details: List[TunjanganDetailDTO] = []
    
    # Dynamic fields for flattened view if needed
    total_tunjangan: Optional[int] = 0

    class Config:
        from_attributes = True

@router.get("/tunjangan", response_model=List[TunjanganDTO])
async def get_tunjangan(
    keyword: Optional[str] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    limit: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(KaryawanTunjangan).join(Karyawan, KaryawanTunjangan.nik == Karyawan.nik)
    
    if keyword:
        query = query.filter(Karyawan.nama_karyawan.like(f"%{keyword}%"))
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
        
    data = query.order_by(desc(KaryawanTunjangan.created_at)).limit(limit).all()
    
    result = []
    for item in data:
        dto = TunjanganDTO.model_validate(item)
        dto.nama_karyawan = item.karyawan.nama_karyawan if item.karyawan else None
        dto.kode_dept = item.karyawan.kode_dept if item.karyawan else None
        dto.kode_cabang = item.karyawan.kode_cabang if item.karyawan else None
        
        # Populate details with join to get names
        details_dto = []
        total = 0
        for d in item.details:
             detail_item = TunjanganDetailDTO(
                 kode_jenis_tunjangan=d.kode_jenis_tunjangan,
                 jumlah=d.jumlah,
                 jenis_tunjangan_nama=d.jenis_tunjangan.jenis_tunjangan if d.jenis_tunjangan else None
             )
             details_dto.append(detail_item)
             total += d.jumlah
        
        dto.details = details_dto
        dto.total_tunjangan = total
        result.append(dto)
        
    return result

@router.post("/tunjangan", response_model=TunjanganDTO)
async def create_tunjangan(payload: CreateTunjanganDTO, db: Session = Depends(get_db)):
    try:
        # Code Generation Logic: T + YY + XXXX
        year_suffix = payload.tanggal_berlaku.strftime('%y') # YY
        prefix = f"T{year_suffix}"
        
        last = db.query(KaryawanTunjangan)\
            .filter(KaryawanTunjangan.kode_tunjangan.like(f"{prefix}%"))\
            .order_by(desc(KaryawanTunjangan.kode_tunjangan))\
            .first()
            
        if last:
            try:
                last_seq = int(last.kode_tunjangan[3:]) 
                new_seq = last_seq + 1
            except ValueError:
                new_seq = 1
        else:
            new_seq = 1
            
        new_code = f"{prefix}{str(new_seq).zfill(4)}"
        
        new_tunjangan = KaryawanTunjangan(
            kode_tunjangan=new_code,
            nik=payload.nik,
            tanggal_berlaku=payload.tanggal_berlaku,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_tunjangan)
        db.flush() # Flush to get PK if needed, though we set it manually
        
        for det in payload.details:
            new_detail = KaryawanTunjanganDetail(
                kode_tunjangan=new_code,
                kode_jenis_tunjangan=det.kode_jenis_tunjangan,
                jumlah=det.jumlah,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_detail)
            
        db.commit()
        db.refresh(new_tunjangan)
        
        # Re-fetch to ensure full data structure
        return await get_tunjangan_by_id(new_code, db)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

async def get_tunjangan_by_id(kode: str, db: Session):
    item = db.query(KaryawanTunjangan).filter(KaryawanTunjangan.kode_tunjangan == kode).first()
    if not item:
        raise HTTPException(status_code=404, detail="Tunjangan not found")
        
    dto = TunjanganDTO.model_validate(item)
    dto.nama_karyawan = item.karyawan.nama_karyawan if item.karyawan else None
    dto.kode_dept = item.karyawan.kode_dept if item.karyawan else None
    dto.kode_cabang = item.karyawan.kode_cabang if item.karyawan else None
    
    details_dto = []
    total = 0
    for d in item.details:
            detail_item = TunjanganDetailDTO(
                kode_jenis_tunjangan=d.kode_jenis_tunjangan,
                jumlah=d.jumlah,
                jenis_tunjangan_nama=d.jenis_tunjangan.jenis_tunjangan if d.jenis_tunjangan else None
            )
            details_dto.append(detail_item)
            total += d.jumlah
    
    dto.details = details_dto
    dto.total_tunjangan = total
    return dto

@router.put("/tunjangan/{kode}", response_model=TunjanganDTO)
async def update_tunjangan(kode: str, payload: UpdateTunjanganDTO, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanTunjangan).filter(KaryawanTunjangan.kode_tunjangan == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="Tunjangan not found")
            
        item.tanggal_berlaku = payload.tanggal_berlaku
        item.updated_at = datetime.now()
        
        # Delete existing details
        db.query(KaryawanTunjanganDetail).filter(KaryawanTunjanganDetail.kode_tunjangan == kode).delete()
        
        # Create new details
        for det in payload.details:
            new_detail = KaryawanTunjanganDetail(
                kode_tunjangan=kode,
                kode_jenis_tunjangan=det.kode_jenis_tunjangan,
                jumlah=det.jumlah,
                created_at=item.created_at, # Keep original created_at? or new? usually new
                updated_at=datetime.now()
            )
            db.add(new_detail)
            
        db.commit()
        db.refresh(item)
        
        return await get_tunjangan_by_id(kode, db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/tunjangan/{kode}")
async def delete_tunjangan(kode: str, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanTunjangan).filter(KaryawanTunjangan.kode_tunjangan == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="Tunjangan not found")
        
        # Details should be deleted by cascade, but explicit delete is safer if cascade not set in DB
        # SQLAlchemy cascade="all, delete-orphan" handles it if loaded, but specific delete query is safer
        db.query(KaryawanTunjanganDetail).filter(KaryawanTunjanganDetail.kode_tunjangan == kode).delete()
        
        db.delete(item)
        db.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# BPJS KESEHATAN
# ==========================================

class CreateBpjsKesehatanDTO(BaseModel):
    nik: str
    jumlah: int
    tanggal_berlaku: date

class UpdateBpjsKesehatanDTO(BaseModel):
    jumlah: int
    tanggal_berlaku: date

class BpjsKesehatanDTO(BaseModel):
    kode_bpjs_kesehatan: str
    nik: str
    nama_karyawan: Optional[str] = None
    kode_dept: Optional[str] = None
    kode_cabang: Optional[str] = None
    jumlah: int
    tanggal_berlaku: date
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.get("/bpjs-kesehatan", response_model=List[BpjsKesehatanDTO])
async def get_bpjs_kesehatan(
    keyword: Optional[str] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    limit: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(KaryawanBpjsKesehatan).join(Karyawan, KaryawanBpjsKesehatan.nik == Karyawan.nik)
    
    if keyword:
        query = query.filter(Karyawan.nama_karyawan.like(f"%{keyword}%"))
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
        
    data = query.order_by(desc(KaryawanBpjsKesehatan.created_at)).limit(limit).all()
    
    result = []
    for item in data:
        dto = BpjsKesehatanDTO.model_validate(item)
        dto.nama_karyawan = item.karyawan.nama_karyawan if item.karyawan else None
        dto.kode_dept = item.karyawan.kode_dept if item.karyawan else None
        dto.kode_cabang = item.karyawan.kode_cabang if item.karyawan else None
        result.append(dto)
        
    return result

@router.post("/bpjs-kesehatan", response_model=BpjsKesehatanDTO)
async def create_bpjs_kesehatan(payload: CreateBpjsKesehatanDTO, db: Session = Depends(get_db)):
    try:
        # Code Generation Logic: K + YY + XXXX
        year_suffix = payload.tanggal_berlaku.strftime('%y') # YY
        prefix = f"K{year_suffix}"
        
        last = db.query(KaryawanBpjsKesehatan)\
            .filter(KaryawanBpjsKesehatan.kode_bpjs_kesehatan.like(f"{prefix}%"))\
            .order_by(desc(KaryawanBpjsKesehatan.kode_bpjs_kesehatan))\
            .first()
            
        if last:
            try:
                last_seq = int(last.kode_bpjs_kesehatan[3:]) 
                new_seq = last_seq + 1
            except ValueError:
                new_seq = 1
        else:
            new_seq = 1
            
        new_code = f"{prefix}{str(new_seq).zfill(4)}"
        
        new_item = KaryawanBpjsKesehatan(
            kode_bpjs_kesehatan=new_code,
            nik=payload.nik,
            jumlah=payload.jumlah,
            tanggal_berlaku=payload.tanggal_berlaku,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        
        dto = BpjsKesehatanDTO.model_validate(new_item)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == payload.nik).first()
        if karyawan:
            dto.nama_karyawan = karyawan.nama_karyawan
            dto.kode_dept = karyawan.kode_dept
            dto.kode_cabang = karyawan.kode_cabang
            
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/bpjs-kesehatan/{kode}", response_model=BpjsKesehatanDTO)
async def update_bpjs_kesehatan(kode: str, payload: UpdateBpjsKesehatanDTO, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanBpjsKesehatan).filter(KaryawanBpjsKesehatan.kode_bpjs_kesehatan == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="BPJS Kesehatan not found")
            
        item.jumlah = payload.jumlah
        item.tanggal_berlaku = payload.tanggal_berlaku
        item.updated_at = datetime.now()
        
        db.commit()
        db.refresh(item)
        
        dto = BpjsKesehatanDTO.model_validate(item)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == item.nik).first()
        if karyawan:
            dto.nama_karyawan = karyawan.nama_karyawan
            dto.kode_dept = karyawan.kode_dept
            dto.kode_cabang = karyawan.kode_cabang
            
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/bpjs-kesehatan/{kode}")
async def delete_bpjs_kesehatan(kode: str, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanBpjsKesehatan).filter(KaryawanBpjsKesehatan.kode_bpjs_kesehatan == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="BPJS Kesehatan not found")
            
        db.delete(item)
        db.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# BPJS TENAGAKERJA
# ==========================================

class CreateBpjsTkDTO(BaseModel):
    nik: str
    jumlah: int
    tanggal_berlaku: date

class UpdateBpjsTkDTO(BaseModel):
    jumlah: int
    tanggal_berlaku: date

class BpjsTkDTO(BaseModel):
    kode_bpjs_tk: str
    nik: str
    nama_karyawan: Optional[str] = None
    kode_dept: Optional[str] = None
    kode_cabang: Optional[str] = None
    jumlah: int
    tanggal_berlaku: date
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.get("/bpjs-tenagakerja", response_model=List[BpjsTkDTO])
async def get_bpjs_tenagakerja(
    keyword: Optional[str] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    limit: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(KaryawanBpjstenagakerja).join(Karyawan, KaryawanBpjstenagakerja.nik == Karyawan.nik)
    
    if keyword:
        query = query.filter(Karyawan.nama_karyawan.like(f"%{keyword}%"))
    if kode_cabang:
        query = query.filter(Karyawan.kode_cabang == kode_cabang)
    if kode_dept:
        query = query.filter(Karyawan.kode_dept == kode_dept)
        
    data = query.order_by(desc(KaryawanBpjstenagakerja.created_at)).limit(limit).all()
    
    result = []
    for item in data:
        dto = BpjsTkDTO.model_validate(item)
        dto.nama_karyawan = item.karyawan.nama_karyawan if item.karyawan else None
        dto.kode_dept = item.karyawan.kode_dept if item.karyawan else None
        dto.kode_cabang = item.karyawan.kode_cabang if item.karyawan else None
        result.append(dto)
        
    return result

@router.post("/bpjs-tenagakerja", response_model=BpjsTkDTO)
async def create_bpjs_tenagakerja(payload: CreateBpjsTkDTO, db: Session = Depends(get_db)):
    try:
        # Code Generation Logic: K + YY + XXXX (same as BPJS Health but for TK table)
        year_suffix = payload.tanggal_berlaku.strftime('%y') # YY
        prefix = f"K{year_suffix}"
        
        last = db.query(KaryawanBpjstenagakerja)\
            .filter(KaryawanBpjstenagakerja.kode_bpjs_tk.like(f"{prefix}%"))\
            .order_by(desc(KaryawanBpjstenagakerja.kode_bpjs_tk))\
            .first()
            
        if last:
            try:
                last_seq = int(last.kode_bpjs_tk[3:]) 
                new_seq = last_seq + 1
            except ValueError:
                new_seq = 1
        else:
            new_seq = 1
            
        new_code = f"{prefix}{str(new_seq).zfill(4)}"
        
        new_item = KaryawanBpjstenagakerja(
            kode_bpjs_tk=new_code,
            nik=payload.nik,
            jumlah=payload.jumlah,
            tanggal_berlaku=payload.tanggal_berlaku,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        
        dto = BpjsTkDTO.model_validate(new_item)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == payload.nik).first()
        if karyawan:
            dto.nama_karyawan = karyawan.nama_karyawan
            dto.kode_dept = karyawan.kode_dept
            dto.kode_cabang = karyawan.kode_cabang
            
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/bpjs-tenagakerja/{kode}", response_model=BpjsTkDTO)
async def update_bpjs_tenagakerja(kode: str, payload: UpdateBpjsTkDTO, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanBpjstenagakerja).filter(KaryawanBpjstenagakerja.kode_bpjs_tk == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="BPJS Tenagakerja not found")
            
        item.jumlah = payload.jumlah
        item.tanggal_berlaku = payload.tanggal_berlaku
        item.updated_at = datetime.now()
        
        db.commit()
        db.refresh(item)
        
        dto = BpjsTkDTO.model_validate(item)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == item.nik).first()
        if karyawan:
            dto.nama_karyawan = karyawan.nama_karyawan
            dto.kode_dept = karyawan.kode_dept
            dto.kode_cabang = karyawan.kode_cabang
            
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/bpjs-tenagakerja/{kode}")
async def delete_bpjs_tenagakerja(kode: str, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanBpjstenagakerja).filter(KaryawanBpjstenagakerja.kode_bpjs_tk == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="BPJS Tenagakerja not found")
            
        db.delete(item)
        db.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# PENYESUAIAN GAJI
# ==========================================

class PenyesuaianGajiDetailDTO(BaseModel):
    kode_penyesuaian_gaji: str
    nik: str
    nama_karyawan: Optional[str] = None
    penambah: int
    pengurang: int
    keterangan: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class CreatePenyesuaianGajiDTO(BaseModel):
    bulan: int
    tahun: int

class UpdatePenyesuaianGajiDTO(BaseModel):
    bulan: int
    tahun: int

class PenyesuaianGajiDTO(BaseModel):
    kode_penyesuaian_gaji: str
    bulan: int
    tahun: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    details: List[PenyesuaianGajiDetailDTO] = []
    
    class Config:
        from_attributes = True

class CreateDetailPenyesuaianDTO(BaseModel):
    nik: str
    penambah: int
    pengurang: int
    keterangan: str

class UpdateDetailPenyesuaianDTO(BaseModel):
    penambah: int
    pengurang: int
    keterangan: str

@router.get("/penyesuaian-gaji", response_model=List[PenyesuaianGajiDTO])
async def get_penyesuaian_gaji(
    tahun: int = Query(datetime.now().year),
    db: Session = Depends(get_db)
):
    data = db.query(KaryawanPenyesuaianGaji)\
        .filter(KaryawanPenyesuaianGaji.tahun == tahun)\
        .order_by(KaryawanPenyesuaianGaji.bulan)\
        .all()
    return data

@router.post("/penyesuaian-gaji", response_model=PenyesuaianGajiDTO)
async def create_penyesuaian_gaji(payload: CreatePenyesuaianGajiDTO, db: Session = Depends(get_db)):
    try:
        # Check existing
        existing = db.query(KaryawanPenyesuaianGaji)\
            .filter(KaryawanPenyesuaianGaji.bulan == payload.bulan, KaryawanPenyesuaianGaji.tahun == payload.tahun)\
            .first()
        if existing:
            raise HTTPException(status_code=400, detail="Data for this period already exists")
            
        bulan_str = str(payload.bulan).zfill(2)
        kode = f"PYG{bulan_str}{payload.tahun}"
        
        new_item = KaryawanPenyesuaianGaji(
            kode_penyesuaian_gaji=kode,
            bulan=payload.bulan,
            tahun=payload.tahun,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/penyesuaian-gaji/{kode}", response_model=PenyesuaianGajiDTO)
async def get_penyesuaian_gaji_by_code(kode: str, db: Session = Depends(get_db)):
    item = db.query(KaryawanPenyesuaianGaji).filter(KaryawanPenyesuaianGaji.kode_penyesuaian_gaji == kode).first()
    if not item:
        raise HTTPException(status_code=404, detail="Data not found")
    return item

@router.put("/penyesuaian-gaji/{kode}", response_model=PenyesuaianGajiDTO)
async def update_penyesuaian_gaji(kode: str, payload: UpdatePenyesuaianGajiDTO, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanPenyesuaianGaji).filter(KaryawanPenyesuaianGaji.kode_penyesuaian_gaji == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="Data not found")
            
        # Check duplicates if changing period
        if item.bulan != payload.bulan or item.tahun != payload.tahun:
            existing = db.query(KaryawanPenyesuaianGaji)\
                .filter(KaryawanPenyesuaianGaji.bulan == payload.bulan, KaryawanPenyesuaianGaji.tahun == payload.tahun)\
                .first()
            if existing:
                raise HTTPException(status_code=400, detail="Data for this period already exists")

        bulan_str = str(payload.bulan).zfill(2)
        new_kode = f"PYG{bulan_str}{payload.tahun}"
        
        # If primary key changes, we might need to recreate or handle cascades. 
        # Ideally, we don't change PKs. But Laravel code does update it.
        # SQLAlchemy doesn't support updating PK directly easily if there are foreign keys without cascade on update.
        # Check FK definition: ON UPDATE CASCADE is set in SQL schema. So we can update PK.
        
        if kode != new_kode:
             # We need to execute raw SQL or use specific methods because modifying PK in ORM is tricky
             # But let's try direct assignment first, relying on ON UPDATE CASCADE
             item.kode_penyesuaian_gaji = new_kode
        
        item.bulan = payload.bulan
        item.tahun = payload.tahun
        item.updated_at = datetime.now()
        
        db.commit()
        db.refresh(item)
        return item
    except HTTPException:
         raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/penyesuaian-gaji/{kode}")
async def delete_penyesuaian_gaji(kode: str, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanPenyesuaianGaji).filter(KaryawanPenyesuaianGaji.kode_penyesuaian_gaji == kode).first()
        if not item:
             raise HTTPException(status_code=404, detail="Data not found")
        db.delete(item)
        db.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
         db.rollback()
         raise HTTPException(status_code=500, detail=str(e))

# Details
@router.get("/penyesuaian-gaji/{kode}/details", response_model=List[PenyesuaianGajiDetailDTO])
async def get_penyesuaian_details(kode: str, db: Session = Depends(get_db)):
    items = db.query(KaryawanPenyesuaianGajiDetail).filter(KaryawanPenyesuaianGajiDetail.kode_penyesuaian_gaji == kode).all()
    result = []
    for item in items:
        dto = PenyesuaianGajiDetailDTO(
            kode_penyesuaian_gaji=item.kode_penyesuaian_gaji,
            nik=item.nik,
            nama_karyawan=item.karyawan.nama_karyawan if item.karyawan else None,
            penambah=item.penambah,
            pengurang=item.pengurang,
            keterangan=item.keterangan,
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        result.append(dto)
    return result

@router.post("/penyesuaian-gaji/{kode}/details", response_model=PenyesuaianGajiDetailDTO)
async def add_penyesuaian_detail(kode: str, payload: CreateDetailPenyesuaianDTO, db: Session = Depends(get_db)):
    try:
        existing = db.query(KaryawanPenyesuaianGajiDetail)\
            .filter(KaryawanPenyesuaianGajiDetail.kode_penyesuaian_gaji == kode, KaryawanPenyesuaianGajiDetail.nik == payload.nik)\
            .first()
        if existing:
            raise HTTPException(status_code=400, detail="Employee already exists in this adjustment period")
            
        new_detail = KaryawanPenyesuaianGajiDetail(
            kode_penyesuaian_gaji=kode,
            nik=payload.nik,
            penambah=payload.penambah,
            pengurang=payload.pengurang,
            keterangan=payload.keterangan,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_detail)
        db.commit()
        db.refresh(new_detail)
        
        dto = PenyesuaianGajiDetailDTO(
            kode_penyesuaian_gaji=new_detail.kode_penyesuaian_gaji,
            nik=new_detail.nik,
            nama_karyawan=new_detail.karyawan.nama_karyawan if new_detail.karyawan else None,
            penambah=new_detail.penambah,
            pengurang=new_detail.pengurang,
            keterangan=new_detail.keterangan,
            created_at=new_detail.created_at,
            updated_at=new_detail.updated_at
        )
        return dto
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/penyesuaian-gaji/{kode}/details/{nik}", response_model=PenyesuaianGajiDetailDTO)
async def update_penyesuaian_detail(kode: str, nik: str, payload: UpdateDetailPenyesuaianDTO, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanPenyesuaianGajiDetail)\
            .filter(KaryawanPenyesuaianGajiDetail.kode_penyesuaian_gaji == kode, KaryawanPenyesuaianGajiDetail.nik == nik)\
            .first()
        if not item:
            raise HTTPException(status_code=404, detail="Detail not found")
            
        item.penambah = payload.penambah
        item.pengurang = payload.pengurang
        item.keterangan = payload.keterangan
        item.updated_at = datetime.now()
        
        db.commit()
        db.refresh(item)
        
        dto = PenyesuaianGajiDetailDTO(
            kode_penyesuaian_gaji=item.kode_penyesuaian_gaji,
            nik=item.nik,
            nama_karyawan=item.karyawan.nama_karyawan if item.karyawan else None,
            penambah=item.penambah,
            pengurang=item.pengurang,
            keterangan=item.keterangan,
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/penyesuaian-gaji/{kode}/details/{nik}")
async def delete_penyesuaian_detail(kode: str, nik: str, db: Session = Depends(get_db)):
    try:
        item = db.query(KaryawanPenyesuaianGajiDetail)\
            .filter(KaryawanPenyesuaianGajiDetail.kode_penyesuaian_gaji == kode, KaryawanPenyesuaianGajiDetail.nik == nik)\
            .first()
        if not item:
            raise HTTPException(status_code=404, detail="Detail not found")
            
        db.delete(item)
        db.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# SLIP GAJI
# ==========================================

class CreateSlipGajiDTO(BaseModel):
    bulan: int
    tahun: int
    status: int

class UpdateSlipGajiDTO(BaseModel):
    bulan: int
    tahun: int
    status: int

class SlipGajiDTO(BaseModel):
    kode_slip_gaji: str
    bulan: int
    tahun: int
    status: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.get("/slip-gaji", response_model=List[SlipGajiDTO])
async def get_slip_gaji(
    db: Session = Depends(get_db)
):
    items = db.query(SlipGaji).order_by(desc(SlipGaji.tahun), desc(SlipGaji.bulan)).all()
    return items

@router.post("/slip-gaji", response_model=SlipGajiDTO)
async def create_slip_gaji(payload: CreateSlipGajiDTO, db: Session = Depends(get_db)):
    try:
        # Check if already exists for the month/year
        existing = db.query(SlipGaji).filter(SlipGaji.bulan == payload.bulan, SlipGaji.tahun == str(payload.tahun)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Slip Gaji for this period already exists")
            
        kode = f"GJ{str(payload.bulan).zfill(2)}{payload.tahun}"
        
        new_item = SlipGaji(
            kode_slip_gaji=kode,
            bulan=payload.bulan,
            tahun=str(payload.tahun),
            status=payload.status,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        return new_item
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/slip-gaji/{kode}", response_model=SlipGajiDTO)
async def get_slip_gaji_by_code(kode: str, db: Session = Depends(get_db)):
    item = db.query(SlipGaji).filter(SlipGaji.kode_slip_gaji == kode).first()
    if not item:
        raise HTTPException(status_code=404, detail="DATA NOT FOUND")
    return item

@router.put("/slip-gaji/{kode}", response_model=SlipGajiDTO)
async def update_slip_gaji(kode: str, payload: UpdateSlipGajiDTO, db: Session = Depends(get_db)):
    try:
        item = db.query(SlipGaji).filter(SlipGaji.kode_slip_gaji == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="DATA NOT FOUND")
        
        # Check duplicate specific to update logic if needed, but primary key is usually consistent or re-generated if period changes.
        # Here assuming simple update.
        
        item.bulan = payload.bulan
        item.tahun = str(payload.tahun)
        item.status = payload.status
        item.updated_at = datetime.now()
        
        db.commit()
        db.refresh(item)
        return item
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/slip-gaji/{kode}")
async def delete_slip_gaji(kode: str, db: Session = Depends(get_db)):
    try:
        item = db.query(SlipGaji).filter(SlipGaji.kode_slip_gaji == kode).first()
        if not item:
            raise HTTPException(status_code=404, detail="DATA NOT FOUND")
            
        db.delete(item)
        db.commit()
        return {"message": "Deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/slip-gaji/{kode}/recap", response_model=List[dict])
async def get_slip_gaji_recap(kode: str, nik: Optional[str] = Query(None), db: Session = Depends(get_db)):
    try:
        slip = db.query(SlipGaji).filter(SlipGaji.kode_slip_gaji == kode).first()
        if not slip:
             raise HTTPException(status_code=404, detail="DATA NOT FOUND")

        # Determine period end date (end of the month)
        import calendar
        last_day = calendar.monthrange(int(slip.tahun), int(slip.bulan))[1]
        periode_sampai = date(int(slip.tahun), int(slip.bulan), last_day)
        
        # 1. Get List of Active Employees
        q = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1')

        if nik:
            q = q.filter(Karyawan.nik == nik)

        employees = q.order_by(Karyawan.nama_karyawan).all()
            
        result = []
        
        for emp in employees:
            # 2. Get Gaji Pokok (Latest valid)
            gaji_pokok_item = db.query(KaryawanGajiPokok)\
                .filter(KaryawanGajiPokok.nik == emp.nik)\
                .filter(KaryawanGajiPokok.tanggal_berlaku <= periode_sampai)\
                .order_by(desc(KaryawanGajiPokok.tanggal_berlaku))\
                .first()
            gaji_pokok = gaji_pokok_item.jumlah if gaji_pokok_item else 0
            
            # 3. Get Tunjangan (Sum of latest per type)
            # Find latest kode_tunjangan for this employee valid for the period
            tunjangan_header = db.query(KaryawanTunjangan)\
                 .filter(KaryawanTunjangan.nik == emp.nik)\
                 .filter(KaryawanTunjangan.tanggal_berlaku <= periode_sampai)\
                 .order_by(desc(KaryawanTunjangan.tanggal_berlaku))\
                 .first()
            
            total_tunjangan = 0
            if tunjangan_header:
                details = db.query(KaryawanTunjanganDetail)\
                    .filter(KaryawanTunjanganDetail.kode_tunjangan == tunjangan_header.kode_tunjangan)\
                    .all()
                total_tunjangan = sum([d.jumlah for d in details])

            # 4. Get BPJS
            bpjs_kes_item = db.query(KaryawanBpjsKesehatan)\
                .filter(KaryawanBpjsKesehatan.nik == emp.nik)\
                .filter(KaryawanBpjsKesehatan.tanggal_berlaku <= periode_sampai)\
                .order_by(desc(KaryawanBpjsKesehatan.tanggal_berlaku))\
                .first()
            bpjs_kes = bpjs_kes_item.jumlah if bpjs_kes_item else 0
            
            bpjs_tk_item = db.query(KaryawanBpjstenagakerja)\
                .filter(KaryawanBpjstenagakerja.nik == emp.nik)\
                .filter(KaryawanBpjstenagakerja.tanggal_berlaku <= periode_sampai)\
                .order_by(desc(KaryawanBpjstenagakerja.tanggal_berlaku))\
                .first()
            bpjs_tk = bpjs_tk_item.jumlah if bpjs_tk_item else 0
            
            # 5. Get Penyesuaian
            # This is specific for this period (month/year)
            # Find kode_penyesuaian_gaji for this month/year
            # PYG + MM + YYYY
            bulan_str = str(slip.bulan).zfill(2)
            kode_pyg = f"PYG{bulan_str}{slip.tahun}"
            
            penyesuaian_item = db.query(KaryawanPenyesuaianGajiDetail)\
                .filter(KaryawanPenyesuaianGajiDetail.kode_penyesuaian_gaji == kode_pyg)\
                .filter(KaryawanPenyesuaianGajiDetail.nik == emp.nik)\
                .first()
            
            penambah = penyesuaian_item.penambah if penyesuaian_item else 0
            pengurang = penyesuaian_item.pengurang if penyesuaian_item else 0
            
            # Calculate Total
            total_penerimaan = gaji_pokok + total_tunjangan + penambah
            total_potongan = bpjs_kes + bpjs_tk + pengurang
            gaji_bersih = total_penerimaan - total_potongan
            
            result.append({
                "nik": emp.nik,
                "nama_karyawan": emp.nama_karyawan,
                "jabatan": emp.jabatan.nama_jabatan if emp.jabatan else "-",
                "gaji_pokok": gaji_pokok,
                "tunjangan": total_tunjangan,
                "bpjs_kesehatan": bpjs_kes,
                "bpjs_tenagakerja": bpjs_tk,
                "penambah": penambah,
                "pengurang": pengurang,
                "gaji_bersih": gaji_bersih
            })
            
        return result

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
