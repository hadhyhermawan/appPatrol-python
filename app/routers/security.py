from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func, text, desc
from app.database import get_db
from app.models.models import Turlalin, Karyawan, SafetyBriefings, Barang, Tamu, PatrolSessions, PatrolSchedules, SuratMasuk, SuratKeluar, PatrolPoints, DepartmentTaskSessions, DepartmentTaskPoints, DepartmentTaskPointMaster, Presensi, SetJamKerjaByDay, SetJamKerjaByDate
from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime, date, time
import os
import secrets
from fastapi.responses import FileResponse

from app.core.permissions import get_current_user

STORAGE_BASE_URL = "https://frontend.k3guard.com/api-py/storage/"

router = APIRouter(
    prefix="/api/security",
    tags=["security"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

# Pydantic Models
class TurlalinDTO(BaseModel):
    id: int
    nomor_polisi: str
    jam_masuk: datetime
    nik: str
    keterangan: Optional[str]
    foto: Optional[str]
    jam_keluar: Optional[datetime]
    nik_keluar: Optional[str]
    foto_keluar: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    # Relationships for display
    nama_guard_masuk: Optional[str] = None
    nama_guard_keluar: Optional[str] = None

    class Config:
        from_attributes = True

class TurlalinCreateRequest(BaseModel):
    nomor_polisi: str
    jam_masuk: datetime
    nik: str
    keterangan: Optional[str] = None
    foto: Optional[str] = None

class TurlalinUpdateRequest(BaseModel):
    nomor_polisi: Optional[str] = None
    jam_masuk: Optional[datetime] = None
    nik: Optional[str] = None
    keterangan: Optional[str] = None
    foto: Optional[str] = None
    jam_keluar: Optional[datetime] = None
    nik_keluar: Optional[str] = None
    foto_keluar: Optional[str] = None

@router.get("/turlalin", response_model=List[TurlalinDTO])
async def get_turlalin_list(
    search: Optional[str] = Query(None, description="Search by No Polisi"),
    date_start: Optional[datetime] = Query(None),
    date_end: Optional[datetime] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Turlalin).outerjoin(Karyawan, Turlalin.nik == Karyawan.nik)
        
        if search:
            query = query.filter(Turlalin.nomor_polisi.like(f"%{search}%"))
        
        if date_start:
            query = query.filter(Turlalin.jam_masuk >= date_start)
        
        if date_end:
            query = query.filter(Turlalin.jam_masuk <= date_end)
            
        if kode_cabang:
            query = query.filter(Karyawan.kode_cabang == kode_cabang)
            
        data = query.order_by(desc(Turlalin.jam_masuk)).limit(100).all()
        
        # Map manually if needed to include guard names not directly in Turlalin model relation lazy loading
        result = []
        for item in data:
            dto = TurlalinDTO.from_orm(item)
            if item.karyawan:
                dto.nama_guard_masuk = item.karyawan.nama_karyawan
            # For keluar guard
            # SQLAlchemy relationship might handle it if defined. Checked model: yes, karyawan_
            if item.karyawan_:
                dto.nama_guard_keluar = item.karyawan_.nama_karyawan
            
            if dto.foto and not dto.foto.startswith(('http', 'https')):
                dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
            if dto.foto_keluar and not dto.foto_keluar.startswith(('http', 'https')):
                dto.foto_keluar = f"{STORAGE_BASE_URL}{dto.foto_keluar}"

            result.append(dto)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/turlalin", response_model=TurlalinDTO)
async def create_turlalin(request: TurlalinCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = Turlalin(
            nomor_polisi=request.nomor_polisi,
            jam_masuk=request.jam_masuk,
            nik=request.nik,
            keterangan=request.keterangan,
            foto=request.foto,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        
        # Populate name manually for response
        dto = TurlalinDTO.from_orm(new_data)
        if new_data.karyawan:
             dto.nama_guard_masuk = new_data.karyawan.nama_karyawan
        
        if dto.foto and not dto.foto.startswith(('http', 'https')):
            dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
             
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Create Turlalin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/turlalin/{id}", response_model=TurlalinDTO)
async def update_turlalin(id: int, request: TurlalinUpdateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(Turlalin).filter(Turlalin.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Turlalin tidak ditemukan")
        
        if request.nomor_polisi is not None: data.nomor_polisi = request.nomor_polisi
        if request.jam_masuk is not None: data.jam_masuk = request.jam_masuk
        if request.nik is not None: data.nik = request.nik
        if request.keterangan is not None: data.keterangan = request.keterangan
        if request.foto is not None: data.foto = request.foto
        if request.jam_keluar is not None: data.jam_keluar = request.jam_keluar
        if request.nik_keluar is not None: data.nik_keluar = request.nik_keluar
        if request.foto_keluar is not None: data.foto_keluar = request.foto_keluar
        
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        
        dto = TurlalinDTO.from_orm(data)
        if data.karyawan:
             dto.nama_guard_masuk = data.karyawan.nama_karyawan
        if data.karyawan_:
             dto.nama_guard_keluar = data.karyawan_.nama_karyawan
        
        if dto.foto and not dto.foto.startswith(('http', 'https')):
            dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
        if dto.foto_keluar and not dto.foto_keluar.startswith(('http', 'https')):
            dto.foto_keluar = f"{STORAGE_BASE_URL}{dto.foto_keluar}"
             
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Update Turlalin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/turlalin/{id}")
async def delete_turlalin(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(Turlalin).filter(Turlalin.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Turlalin tidak ditemukan")
        
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data Turlalin berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Turlalin: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# SAFETY BRIEFING
# ==========================================

class SafetyBriefingDTO(BaseModel):
    id: int
    nik: str
    keterangan: str
    tanggal_jam: datetime
    foto: Optional[str] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    # Karyawan Rel
    nama_karyawan: Optional[str] = None
    
    class Config:
        from_attributes = True

class SafetyBriefingCreateRequest(BaseModel):
    nik: str
    keterangan: str
    tanggal_jam: datetime
    foto: Optional[str] = None

class SafetyBriefingUpdateRequest(BaseModel):
    nik: Optional[str] = None
    keterangan: Optional[str] = None
    tanggal_jam: Optional[datetime] = None
    foto: Optional[str] = None

@router.get("/safety-briefings", response_model=List[SafetyBriefingDTO])
async def get_safety_briefings(
    search: Optional[str] = Query(None, description="Search by Keterangan/Nama"),
    date_start: Optional[datetime] = Query(None),
    date_end: Optional[datetime] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(SafetyBriefings).outerjoin(Karyawan, SafetyBriefings.nik == Karyawan.nik)
        
        if search:
            query = query.filter((SafetyBriefings.keterangan.like(f"%{search}%")) | (Karyawan.nama_karyawan.like(f"%{search}%")))
            
        if date_start:
            query = query.filter(SafetyBriefings.tanggal_jam >= date_start)
            
        if date_end:
            query = query.filter(SafetyBriefings.tanggal_jam <= date_end)
            
        if kode_cabang:
            query = query.filter(Karyawan.kode_cabang == kode_cabang)
            
        data = query.order_by(desc(SafetyBriefings.tanggal_jam)).limit(100).all()
        
        result = []
        for item in data:
            dto = SafetyBriefingDTO.from_orm(item)
            if item.karyawan:
                dto.nama_karyawan = item.karyawan.nama_karyawan
            
            if dto.foto and not dto.foto.startswith(('http', 'https')):
                dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
                
            result.append(dto)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/safety-briefings", response_model=SafetyBriefingDTO)
async def create_safety_briefing(request: SafetyBriefingCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = SafetyBriefings(
            nik=request.nik,
            keterangan=request.keterangan,
            tanggal_jam=request.tanggal_jam,
            foto=request.foto,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        
        dto = SafetyBriefingDTO.from_orm(new_data)
        if new_data.karyawan:
            dto.nama_karyawan = new_data.karyawan.nama_karyawan

        if dto.foto and not dto.foto.startswith(('http', 'https')):
            dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
        
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Create Safety Briefing: {str(e)}")
        if "foreign key constraint" in str(e).lower():
             raise HTTPException(status_code=400, detail="NIK Karyawan tidak valid")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/safety-briefings/{id}", response_model=SafetyBriefingDTO)
async def update_safety_briefing(id: int, request: SafetyBriefingUpdateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(SafetyBriefings).filter(SafetyBriefings.id == id).first()
        if not data:
             raise HTTPException(status_code=404, detail="Safety Briefing tidak ditemukan")
             
        if request.nik is not None: data.nik = request.nik
        if request.keterangan is not None: data.keterangan = request.keterangan
        if request.tanggal_jam is not None: data.tanggal_jam = request.tanggal_jam
        if request.foto is not None: data.foto = request.foto
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        
        dto = SafetyBriefingDTO.from_orm(data)
        if data.karyawan:
            dto.nama_karyawan = data.karyawan.nama_karyawan
        
        if dto.foto and not dto.foto.startswith(('http', 'https')):
            dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
            
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Update Safety Briefing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/safety-briefings/{id}")
async def delete_safety_briefing(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(SafetyBriefings).filter(SafetyBriefings.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Safety Briefing tidak ditemukan")
            
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Safety Briefing berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Safety Briefing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# BARANG (LOG BOOK)
# ==========================================

class BarangDTO(BaseModel):
    id_barang: int
    jenis_barang: str
    dari: str
    untuk: str
    kode_cabang: Optional[str]
    penerima: Optional[str]
    image: Optional[str]
    foto_keluar: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    petugas_penerima: Optional[str] = None
    petugas_keluar: Optional[str] = None
    
    class Config:
        from_attributes = True

class BarangCreateRequest(BaseModel):
    jenis_barang: str
    dari: str
    untuk: str
    kode_cabang: Optional[str] = None
    penerima: Optional[str] = None
    image: Optional[str] = None
    foto_keluar: Optional[str] = None
    
@router.get("/barang", response_model=List[BarangDTO])
async def get_barang_list(
    search: Optional[str] = Query(None, description="Search by ID/Jenis/Dari/Untuk"),
    date_start: Optional[datetime] = Query(None),
    date_end: Optional[datetime] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    limit: Optional[int] = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Barang)
        
        if search:
            query = query.filter(
                (Barang.jenis_barang.like(f"%{search}%")) |
                (Barang.dari.like(f"%{search}%")) |
                (Barang.untuk.like(f"%{search}%"))
            )
            
        if date_start:
            query = query.filter(Barang.created_at >= date_start)
            
        if date_end:
            query = query.filter(Barang.created_at <= date_end)
            
        if kode_cabang:
            query = query.filter(Barang.kode_cabang == kode_cabang)
            
        data = query.order_by(desc(Barang.created_at)).limit(limit).all()
        result = []
        for item in data:
            dto = BarangDTO.from_orm(item)
            if item.barang_masuk and item.barang_masuk[0].karyawan:
                dto.petugas_penerima = item.barang_masuk[0].karyawan.nama_karyawan
            if item.barang_keluar and item.barang_keluar[0].karyawan:
                dto.petugas_keluar = item.barang_keluar[0].karyawan.nama_karyawan
                
            if dto.image and not dto.image.startswith(('http', 'https')):
                dto.image = f"{STORAGE_BASE_URL}{dto.image}"
            if dto.foto_keluar and not dto.foto_keluar.startswith(('http', 'https')):
                dto.foto_keluar = f"{STORAGE_BASE_URL}{dto.foto_keluar}"
            result.append(dto)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/barang", response_model=BarangDTO)
async def create_barang(request: BarangCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = Barang(
            jenis_barang=request.jenis_barang,
            dari=request.dari,
            untuk=request.untuk,
            kode_cabang=request.kode_cabang,
            penerima=request.penerima,
            image=request.image,
            foto_keluar=request.foto_keluar,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        return new_data
    except Exception as e:
        db.rollback()
        print(f"Error Create Barang: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/barang/{id}", response_model=BarangDTO)
async def update_barang(id: int, request: BarangCreateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(Barang).filter(Barang.id_barang == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Barang tidak ditemukan")
            
        data.jenis_barang = request.jenis_barang
        data.dari = request.dari
        data.untuk = request.untuk
        if request.kode_cabang is not None: data.kode_cabang = request.kode_cabang
        if request.penerima is not None: data.penerima = request.penerima
        if request.image is not None: data.image = request.image
        if request.foto_keluar is not None: data.foto_keluar = request.foto_keluar
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        return data
    except Exception as e:
        db.rollback()
        print(f"Error Update Barang: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/barang/{id}")
async def delete_barang(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(Barang).filter(Barang.id_barang == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Barang tidak ditemukan")
            
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data Barang berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Barang: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# TAMU (GUEST BOOK)
# ==========================================

class TamuDTO(BaseModel):
    id_tamu: int
    nama: str
    alamat: Optional[str]
    jenis_id: Optional[str]
    no_telp: Optional[str]
    perusahaan: Optional[str]
    bertemu_dengan: Optional[str]
    dengan_perjanjian: Optional[str]
    keperluan: Optional[str]
    jenis_kendaraan: Optional[str]
    no_pol: Optional[str]
    foto: Optional[str]
    foto_keluar: Optional[str]
    barcode_kartu: Optional[str]
    jam_masuk: Optional[datetime]
    jam_keluar: Optional[datetime]
    nik_satpam: Optional[str]
    nik_satpam_keluar: Optional[str]
    
    # Relationships
    nama_satpam_masuk: Optional[str] = None
    
    class Config:
        from_attributes = True

class TamuCreateRequest(BaseModel):
    nama: str
    alamat: Optional[str] = None
    jenis_id: Optional[str] = None
    no_telp: Optional[str] = None
    perusahaan: Optional[str] = None
    bertemu_dengan: Optional[str] = None
    dengan_perjanjian: Optional[str] = 'TIDAK'
    keperluan: Optional[str] = None
    jenis_kendaraan: Optional[str] = 'PEJALAN KAKI'
    no_pol: Optional[str] = None
    foto: Optional[str] = None
    foto_keluar: Optional[str] = None
    barcode_kartu: Optional[str] = None
    jam_masuk: Optional[datetime] = None
    jam_keluar: Optional[datetime] = None
    nik_satpam: Optional[str] = None
    nik_satpam_keluar: Optional[str] = None

@router.get("/tamu", response_model=List[TamuDTO])
async def get_tamu_list(
    search: Optional[str] = Query(None, description="Search by Nama/Perusahaan/Keperluan"),
    date_start: Optional[datetime] = Query(None),
    date_end: Optional[datetime] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    limit: Optional[int] = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Tamu).outerjoin(Karyawan, Tamu.nik_satpam == Karyawan.nik)
        
        if search:
            query = query.filter(
                (Tamu.nama.like(f"%{search}%")) |
                (Tamu.perusahaan.like(f"%{search}%")) |
                (Tamu.keperluan.like(f"%{search}%"))
            )
            
        if date_start:
            query = query.filter(Tamu.jam_masuk >= date_start)
            
        if date_end:
            query = query.filter(Tamu.jam_masuk <= date_end)
            
        if kode_cabang:
            query = query.filter(Karyawan.kode_cabang == kode_cabang)
            
        data = query.order_by(desc(Tamu.jam_masuk)).limit(limit).all()
        
        result = []
        for item in data:
            dto = TamuDTO.from_orm(item)
            if item.karyawan:
                dto.nama_satpam_masuk = item.karyawan.nama_karyawan
            result.append(dto)

        # Fix Image URLs for Tamu
        for dto in result:
             if dto.foto and not dto.foto.startswith(('http', 'https')):
                dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
             if dto.foto_keluar and not dto.foto_keluar.startswith(('http', 'https')):
                dto.foto_keluar = f"{STORAGE_BASE_URL}{dto.foto_keluar}"
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tamu", response_model=TamuDTO)
async def create_tamu(request: TamuCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = Tamu(
            nama=request.nama,
            alamat=request.alamat,
            jenis_id=request.jenis_id,
            no_telp=request.no_telp,
            perusahaan=request.perusahaan,
            bertemu_dengan=request.bertemu_dengan,
            dengan_perjanjian=request.dengan_perjanjian,
            keperluan=request.keperluan,
            jenis_kendaraan=request.jenis_kendaraan,
            no_pol=request.no_pol,
            foto=request.foto,
            foto_keluar=request.foto_keluar,
            barcode_kartu=request.barcode_kartu,
            jam_masuk=request.jam_masuk or datetime.now(),
            jam_keluar=request.jam_keluar,
            nik_satpam=request.nik_satpam,
            nik_satpam_keluar=request.nik_satpam_keluar
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        
        dto = TamuDTO.from_orm(new_data)
        if new_data.karyawan:
            dto.nama_satpam_masuk = new_data.karyawan.nama_karyawan
            
        if dto.foto and not dto.foto.startswith(('http', 'https')):
             dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
        if dto.foto_keluar and not dto.foto_keluar.startswith(('http', 'https')):
             dto.foto_keluar = f"{STORAGE_BASE_URL}{dto.foto_keluar}"

        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Create Tamu: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/tamu/{id}", response_model=TamuDTO)
async def update_tamu(id: int, request: TamuCreateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(Tamu).filter(Tamu.id_tamu == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Tamu tidak ditemukan")
            
        if request.nama is not None: data.nama = request.nama
        if request.alamat is not None: data.alamat = request.alamat
        if request.jenis_id is not None: data.jenis_id = request.jenis_id
        if request.no_telp is not None: data.no_telp = request.no_telp
        if request.perusahaan is not None: data.perusahaan = request.perusahaan
        if request.bertemu_dengan is not None: data.bertemu_dengan = request.bertemu_dengan
        if request.dengan_perjanjian is not None: data.dengan_perjanjian = request.dengan_perjanjian
        if request.keperluan is not None: data.keperluan = request.keperluan
        if request.jenis_kendaraan is not None: data.jenis_kendaraan = request.jenis_kendaraan
        if request.no_pol is not None: data.no_pol = request.no_pol
        if request.foto is not None: data.foto = request.foto
        if request.foto_keluar is not None: data.foto_keluar = request.foto_keluar
        if request.barcode_kartu is not None: data.barcode_kartu = request.barcode_kartu
        if request.jam_masuk is not None: data.jam_masuk = request.jam_masuk
        if request.jam_keluar is not None: data.jam_keluar = request.jam_keluar
        if request.nik_satpam is not None: data.nik_satpam = request.nik_satpam
        if request.nik_satpam_keluar is not None: data.nik_satpam_keluar = request.nik_satpam_keluar
        
        db.commit()
        db.refresh(data)
        
        dto = TamuDTO.from_orm(data)
        if data.karyawan:
            dto.nama_satpam_masuk = data.karyawan.nama_karyawan
            
        if dto.foto and not dto.foto.startswith(('http', 'https')):
             dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
        if dto.foto_keluar and not dto.foto_keluar.startswith(('http', 'https')):
             dto.foto_keluar = f"{STORAGE_BASE_URL}{dto.foto_keluar}"
             
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Update Tamu: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/tamu/{id}")
async def delete_tamu(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(Tamu).filter(Tamu.id_tamu == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Tamu tidak ditemukan")
            
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data Tamu berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Tamu: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# PATROL SESSIONS (MONITORING PATROLI)
# ==========================================
from datetime import date, time

class PatrolSessionDTO(BaseModel):
    id: int
    nik: str
    tanggal: date
    kode_jam_kerja: str
    jam_patrol: time
    status: str
    foto_absen: Optional[str]
    lokasi_absen: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    # Karyawan Info
    nama_petugas: Optional[str] = None
    kode_cabang: Optional[str] = None
    nama_cabang: Optional[str] = None
    
    class Config:
        from_attributes = True
        orm_mode = True

class PatrolSessionCreateRequest(BaseModel):
    nik: str
    tanggal: date
    kode_jam_kerja: str
    jam_patrol: time
    status: str = 'active'
    foto_absen: Optional[str] = None
    lokasi_absen: Optional[str] = None

@router.get("/patrol", response_model=List[PatrolSessionDTO])
async def get_patrol_list(
    search: Optional[str] = Query(None, description="Search by NIK/Nama"),
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    kode_cabang: Optional[str] = Query(None, description="Filter by Kode Cabang"),
    kode_jam_kerja: Optional[str] = Query(None, description="Filter by Kode Jam Kerja (Shift)"),
    limit: Optional[int] = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    try:
        print(f"DEBUG PATROL REQUEST: search='{search}', date_start={date_start}, date_end={date_end}, limit={limit}")
        query = db.query(PatrolSessions).outerjoin(Karyawan, PatrolSessions.nik == Karyawan.nik)
        
        if search:
            query = query.filter(
                (PatrolSessions.nik.like(f"%{search}%")) |
                (Karyawan.nama_karyawan.like(f"%{search}%"))
            )
            
        if date_start:
            query = query.filter(PatrolSessions.tanggal >= date_start)
            
        if date_end:
            query = query.filter(PatrolSessions.tanggal <= date_end)

        if kode_cabang:
            query = query.filter(Karyawan.kode_cabang == kode_cabang)

        if kode_jam_kerja:
            query = query.filter(PatrolSessions.kode_jam_kerja == kode_jam_kerja)
            
        data = query.order_by(desc(PatrolSessions.created_at)).limit(limit).all()
        print(f"DEBUG PATROL QUERY FOUND: {len(data)} items")
        
        result = []
        for item in data:
            try:
                dto = PatrolSessionDTO.from_orm(item)
                # Fetch name manually or via relationship if exists. Since join is used, can access if joined object is returned.
                # But query(PatrolSessions) only returns PatrolSessions.
                # Let's fetch name separately or assume standard join if we select both.
                # Optimization: Fetch name for each
                karyawan = db.query(Karyawan).filter(Karyawan.nik == item.nik).first()
                if karyawan:
                    dto.nama_petugas = karyawan.nama_karyawan
                    dto.kode_cabang = karyawan.kode_cabang
                    # Ambil nama cabang dari model Cabang
                    from app.models.models import Cabang
                    cabang = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
                    if cabang:
                        dto.nama_cabang = cabang.nama_cabang
                
                # Construct Foto Absen URL
                if item.foto_absen:
                    ymd = item.tanggal.strftime('%Y%m%d')
                    folder = f"{item.nik}-{ymd}-absenpatrol"
                    filename = os.path.basename(item.foto_absen)
                    # Static path handling
                    dto.foto_absen = f"https://frontend.k3guard.com/api-py/storage/uploads/patroli/{folder}/{filename}"

                result.append(dto)
            except Exception as e:
                print(f"SKIPPING ERROR ITEM ID {getattr(item, 'id', 'unknown')}: {str(e)}")
                continue
            
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/patrol", response_model=PatrolSessionDTO)
async def create_patrol(request: PatrolSessionCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = PatrolSessions(
            nik=request.nik,
            tanggal=request.tanggal,
            kode_jam_kerja=request.kode_jam_kerja,
            jam_patrol=request.jam_patrol,
            status=request.status,
            foto_absen=request.foto_absen,
            lokasi_absen=request.lokasi_absen,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        
        dto = PatrolSessionDTO.from_orm(new_data)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == new_data.nik).first()
        if karyawan:
            dto.nama_petugas = karyawan.nama_karyawan
            
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Create Patrol: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/patrol/{id}", response_model=PatrolSessionDTO)
async def update_patrol(id: int, request: PatrolSessionCreateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(PatrolSessions).filter(PatrolSessions.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Patrol tidak ditemukan")
            
        if request.nik is not None: data.nik = request.nik
        if request.tanggal is not None: data.tanggal = request.tanggal
        if request.kode_jam_kerja is not None: data.kode_jam_kerja = request.kode_jam_kerja
        if request.jam_patrol is not None: data.jam_patrol = request.jam_patrol
        if request.status is not None: data.status = request.status
        if request.foto_absen is not None: data.foto_absen = request.foto_absen
        if request.lokasi_absen is not None: data.lokasi_absen = request.lokasi_absen
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        
        dto = PatrolSessionDTO.from_orm(data)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == data.nik).first()
        if karyawan:
            dto.nama_petugas = karyawan.nama_karyawan
            
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Update Patrol: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/patrol/{id}")
async def delete_patrol(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(PatrolSessions).filter(PatrolSessions.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Patrol tidak ditemukan")
            
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data Patrol berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Patrol: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MANAJEMEN REGU (TEAMS / SCHEDULES)
# ==========================================

class PatrolScheduleDTO(BaseModel):
    id: int
    kode_jam_kerja: str
    start_time: time
    end_time: time
    is_active: int
    kode_dept: Optional[str]
    kode_cabang: Optional[str]
    name: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class PatrolScheduleCreateRequest(BaseModel):
    kode_jam_kerja: str
    start_time: time
    end_time: time
    is_active: Optional[int] = 1
    kode_dept: Optional[str] = None
    kode_cabang: Optional[str] = None
    name: Optional[str] = None

@router.get("/schedules", response_model=List[PatrolScheduleDTO])
async def get_patrol_schedules(
    search: Optional[str] = Query(None, description="Search by Name/Kode Jam Kerja"),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(PatrolSchedules)
        
        if search:
            query = query.filter(
                (PatrolSchedules.name.like(f"%{search}%")) |
                (PatrolSchedules.kode_jam_kerja.like(f"%{search}%"))
            )
            
        data = query.order_by(PatrolSchedules.kode_jam_kerja).all()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schedules", response_model=PatrolScheduleDTO)
async def create_patrol_schedule(request: PatrolScheduleCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = PatrolSchedules(
            kode_jam_kerja=request.kode_jam_kerja,
            start_time=request.start_time,
            end_time=request.end_time,
            is_active=request.is_active,
            kode_dept=request.kode_dept,
            kode_cabang=request.kode_cabang,
            name=request.name
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        return new_data
    except Exception as e:
        db.rollback()
        print(f"Error Create Schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/schedules/{id}", response_model=PatrolScheduleDTO)
async def update_patrol_schedule(id: int, request: PatrolScheduleCreateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(PatrolSchedules).filter(PatrolSchedules.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Schedule tidak ditemukan")
            
        data.kode_jam_kerja = request.kode_jam_kerja
        data.start_time = request.start_time
        data.end_time = request.end_time
        if request.is_active is not None: data.is_active = request.is_active
        if request.kode_dept is not None: data.kode_dept = request.kode_dept
        if request.kode_cabang is not None: data.kode_cabang = request.kode_cabang
        if request.name is not None: data.name = request.name
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        return data
    except Exception as e:
        db.rollback()
        print(f"Error Update Schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/schedules/{id}")
async def delete_patrol_schedule(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(PatrolSchedules).filter(PatrolSchedules.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Schedule tidak ditemukan")
            
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data Schedule berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# SURAT MASUK & KELUAR
# ==========================================

class SuratMasukDTO(BaseModel):
    id: int
    nomor_surat: str
    tanggal_surat: datetime
    asal_surat: str
    tujuan_surat: str
    perihal: str
    nik_satpam: str
    foto: Optional[str]
    nik_satpam_pengantar: Optional[str]
    nama_penerima: Optional[str]
    no_penerima: Optional[str]
    foto_penerima: Optional[str]
    status_surat: Optional[str]
    tanggal_update: Optional[datetime]
    status_penerimaan: Optional[str]
    tanggal_diterima: Optional[datetime]
    
    # Karyawan Info
    nama_satpam: Optional[str] = None
    
    class Config:
        from_attributes = True

class SuratKeluarDTO(BaseModel):
    id: int
    nomor_surat: str
    tanggal_surat: datetime
    tujuan_surat: str
    perihal: str
    nik_satpam: str
    foto: Optional[str]
    foto_penerima: Optional[str]
    nik_satpam_pengantar: Optional[str]
    nama_penerima: Optional[str]
    no_penerima: Optional[str]
    status_surat: Optional[str]
    tanggal_update: Optional[datetime]
    status_penerimaan: Optional[str]
    tanggal_diterima: Optional[datetime]
    
    nama_satpam: Optional[str] = None

    class Config:
        from_attributes = True

class SuratCreateRequest(BaseModel):
    nomor_surat: str
    tanggal_surat: datetime
    asal_surat: Optional[str] = None # Only for SuratMasuk
    tujuan_surat: str
    perihal: str
    nik_satpam: str
    foto: Optional[str] = None
    nik_satpam_pengantar: Optional[str] = None
    nama_penerima: Optional[str] = None
    no_penerima: Optional[str] = None
    foto_penerima: Optional[str] = None
    status_surat: Optional[str] = 'MASUK' # Or KELUAR
    status_penerimaan: Optional[str] = 'BELUM'

# Surat Masuk Endpoints
@router.get("/surat-masuk", response_model=List[SuratMasukDTO])
async def get_surat_masuk(
    search: Optional[str] = Query(None, description="Search by No Surat/Asal/Perihal"),
    date_start: Optional[datetime] = Query(None),
    date_end: Optional[datetime] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    limit: Optional[int] = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(SuratMasuk).outerjoin(Karyawan, SuratMasuk.nik_satpam == Karyawan.nik)
        if search:
            query = query.filter(
                (SuratMasuk.nomor_surat.like(f"%{search}%")) |
                (SuratMasuk.asal_surat.like(f"%{search}%")) |
                (SuratMasuk.perihal.like(f"%{search}%"))
            )
        
        if date_start:
            query = query.filter(SuratMasuk.tanggal_surat >= date_start)
            
        if date_end:
            query = query.filter(SuratMasuk.tanggal_surat <= date_end)
            
        if kode_cabang:
            query = query.filter(Karyawan.kode_cabang == kode_cabang)
            
        data = query.order_by(desc(SuratMasuk.tanggal_surat)).limit(limit).all()
        result = []
        for item in data:
            dto = SuratMasukDTO.from_orm(item)
            if item.karyawan:
                dto.nama_satpam = item.karyawan.nama_karyawan
            
            if dto.foto and not dto.foto.startswith(('http', 'https')):
                dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
            if dto.foto_penerima and not dto.foto_penerima.startswith(('http', 'https')):
                dto.foto_penerima = f"{STORAGE_BASE_URL}{dto.foto_penerima}"
                
            result.append(dto)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/surat-masuk", response_model=SuratMasukDTO)
async def create_surat_masuk(request: SuratCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = SuratMasuk(
            nomor_surat=request.nomor_surat,
            tanggal_surat=request.tanggal_surat,
            asal_surat=request.asal_surat or "",
            tujuan_surat=request.tujuan_surat,
            perihal=request.perihal,
            nik_satpam=request.nik_satpam,
            foto=request.foto,
            nik_satpam_pengantar=request.nik_satpam_pengantar,
            nama_penerima=request.nama_penerima,
            no_penerima=request.no_penerima,
            foto_penerima=request.foto_penerima,
            status_surat=request.status_surat or 'MASUK',
            status_penerimaan=request.status_penerimaan or 'BELUM'
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        dto = SuratMasukDTO.from_orm(new_data)
        if new_data.karyawan:
             dto.nama_satpam = new_data.karyawan.nama_karyawan
        
        if dto.foto and not dto.foto.startswith(('http', 'https')):
            dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
        if dto.foto_penerima and not dto.foto_penerima.startswith(('http', 'https')):
            dto.foto_penerima = f"{STORAGE_BASE_URL}{dto.foto_penerima}"
             
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Create Surat Masuk: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
@router.put("/surat-masuk/{id}", response_model=SuratMasukDTO)
async def update_surat_masuk(id: int, request: SuratCreateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(SuratMasuk).filter(SuratMasuk.id == id).first()
        if not data:
             raise HTTPException(status_code=404, detail="Data Surat Masuk tidak ditemukan")
        
        data.nomor_surat = request.nomor_surat
        data.tanggal_surat = request.tanggal_surat
        if request.asal_surat: data.asal_surat = request.asal_surat
        data.tujuan_surat = request.tujuan_surat
        data.perihal = request.perihal
        data.nik_satpam = request.nik_satpam
        if request.foto: data.foto = request.foto
        data.nik_satpam_pengantar = request.nik_satpam_pengantar
        data.nama_penerima = request.nama_penerima
        data.no_penerima = request.no_penerima
        if request.foto_penerima: data.foto_penerima = request.foto_penerima
        data.status_surat = request.status_surat
        data.status_penerimaan = request.status_penerimaan
        data.tanggal_update = datetime.now()
        
        db.commit()
        db.refresh(data)
        dto = SuratMasukDTO.from_orm(data)
        if data.karyawan:
             dto.nama_satpam = data.karyawan.nama_karyawan
        
        if dto.foto and not dto.foto.startswith(('http', 'https')):
            dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
        if dto.foto_penerima and not dto.foto_penerima.startswith(('http', 'https')):
            dto.foto_penerima = f"{STORAGE_BASE_URL}{dto.foto_penerima}"
             
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/surat-masuk/{id}")
async def delete_surat_masuk(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(SuratMasuk).filter(SuratMasuk.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Surat Masuk tidak ditemukan")
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Surat Keluar Endpoints
@router.get("/surat-keluar", response_model=List[SuratKeluarDTO])
async def get_surat_keluar(
    search: Optional[str] = Query(None, description="Search by No Surat/Perihal"),
    date_start: Optional[datetime] = Query(None),
    date_end: Optional[datetime] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    limit: Optional[int] = Query(100, le=1000),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(SuratKeluar).outerjoin(Karyawan, SuratKeluar.nik_satpam == Karyawan.nik)
        if search:
            query = query.filter(
                (SuratKeluar.nomor_surat.like(f"%{search}%")) |
                (SuratKeluar.perihal.like(f"%{search}%"))
            )
            
        if date_start:
            query = query.filter(SuratKeluar.tanggal_surat >= date_start)
            
        if date_end:
            query = query.filter(SuratKeluar.tanggal_surat <= date_end)
            
        if kode_cabang:
            query = query.filter(Karyawan.kode_cabang == kode_cabang)
            
        data = query.order_by(desc(SuratKeluar.tanggal_surat)).limit(limit).all()
        result = []
        for item in data:
            dto = SuratKeluarDTO.from_orm(item)
            if item.karyawan:
                dto.nama_satpam = item.karyawan.nama_karyawan
            
            if dto.foto and not dto.foto.startswith(('http', 'https')):
                dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
            if dto.foto_penerima and not dto.foto_penerima.startswith(('http', 'https')):
                dto.foto_penerima = f"{STORAGE_BASE_URL}{dto.foto_penerima}"
                
            result.append(dto)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/surat-keluar", response_model=SuratKeluarDTO)
async def create_surat_keluar(request: SuratCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = SuratKeluar(
            nomor_surat=request.nomor_surat,
            tanggal_surat=request.tanggal_surat,
            tujuan_surat=request.tujuan_surat,
            perihal=request.perihal,
            nik_satpam=request.nik_satpam,
            foto=request.foto,
            nik_satpam_pengantar=request.nik_satpam_pengantar,
            nama_penerima=request.nama_penerima,
            no_penerima=request.no_penerima,
            foto_penerima=request.foto_penerima,
            status_surat=request.status_surat or 'KELUAR',
            status_penerimaan=request.status_penerimaan or 'BELUM'
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        dto = SuratKeluarDTO.from_orm(new_data)
        if new_data.karyawan:
             dto.nama_satpam = new_data.karyawan.nama_karyawan
        
        if dto.foto and not dto.foto.startswith(('http', 'https')):
            dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
        if dto.foto_penerima and not dto.foto_penerima.startswith(('http', 'https')):
            dto.foto_penerima = f"{STORAGE_BASE_URL}{dto.foto_penerima}"
             
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Create Surat Keluar: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/surat-keluar/{id}", response_model=SuratKeluarDTO)
async def update_surat_keluar(id: int, request: SuratCreateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(SuratKeluar).filter(SuratKeluar.id == id).first()
        if not data:
             raise HTTPException(status_code=404, detail="Data Surat Keluar tidak ditemukan")
        
        data.nomor_surat = request.nomor_surat
        data.tanggal_surat = request.tanggal_surat
        data.tujuan_surat = request.tujuan_surat
        data.perihal = request.perihal
        data.nik_satpam = request.nik_satpam
        if request.foto: data.foto = request.foto
        data.nik_satpam_pengantar = request.nik_satpam_pengantar
        data.nama_penerima = request.nama_penerima
        data.no_penerima = request.no_penerima
        if request.foto_penerima: data.foto_penerima = request.foto_penerima
        data.status_surat = request.status_surat
        data.status_penerimaan = request.status_penerimaan
        data.tanggal_update = datetime.now()
        
        db.commit()
        db.refresh(data)
        dto = SuratKeluarDTO.from_orm(data)
        if data.karyawan:
             dto.nama_satpam = data.karyawan.nama_karyawan
        
        if dto.foto and not dto.foto.startswith(('http', 'https')):
            dto.foto = f"{STORAGE_BASE_URL}{dto.foto}"
        if dto.foto_penerima and not dto.foto_penerima.startswith(('http', 'https')):
            dto.foto_penerima = f"{STORAGE_BASE_URL}{dto.foto_penerima}"
             
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/surat-keluar/{id}")
async def delete_surat_keluar(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(SuratKeluar).filter(SuratKeluar.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Surat Keluar tidak ditemukan")
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MAP TRACKING (MONITORING LOKASI PATROLI)
# ==========================================

class PatrolTrackingDTO(BaseModel):
    id: int
    patrol_session_id: int
    patrol_point_master_id: Optional[int] = None
    check_time: Optional[datetime] = None
    location_lat: Optional[str] = None
    location_long: Optional[str] = None
    status_aman: Optional[int] = 1 # Default to Aman
    keterangan: Optional[str] = None
    foto: Optional[str] = None
    
    # Extra info
    nik: Optional[str] = None
    nama_petugas: Optional[str] = None
    point_name: Optional[str] = None
    
    class Config:
        from_attributes = True

@router.get("/tracking", response_model=List[PatrolTrackingDTO])
async def get_patrol_tracking(
    date_filter: Optional[date] = Query(None),
    nik: Optional[str] = Query(None),
    limit: Optional[int] = Query(500),
    db: Session = Depends(get_db)
):
    try:
        # Join PatrolPoints -> PatrolSessions -> Karyawan (optional)
        # Also PatrolPoints -> PatrolPointMaster (for point name)
        
        query = db.query(PatrolPoints)
        
        today = date_filter or date.today()
        
        # Filter by date on created_at or join session date
        # PatrolPoints.created_at is timestamp
        query = query.filter(func.date(PatrolPoints.created_at) == today)
        
        if nik:
             # Need to join with PatrolSessions to filter by NIK
             query = query.join(PatrolSessions, PatrolPoints.patrol_session_id == PatrolSessions.id).filter(PatrolSessions.nik == nik)
             
        data = query.order_by(PatrolPoints.created_at).limit(limit).all()
        
        result = []
        for item in data:
            # Manually map since model fields differ from DTO
            dto = PatrolTrackingDTO(
                id=item.id,
                patrol_session_id=item.patrol_session_id,
                patrol_point_master_id=item.patrol_point_master_id,
                check_time=item.created_at,
                foto=item.foto,
                status_aman=1, # Default safe as column missing
                keterangan="Checkpoint Check" # Default
            )
            
            # Parse Location
            if item.lokasi and ',' in item.lokasi:
                try:
                    lat, long = item.lokasi.split(',', 1)
                    dto.location_lat = lat.strip()
                    dto.location_long = long.strip()
                except:
                    pass
            
            # Manually populate extra fields if relations are loaded or accessible
            if item.patrol_session:
                dto.nik = item.patrol_session.nik
                # Fetch name if possible, or skip to optimize.
                # Assuming simple eager load or separate query if needed.
                pass

            # Fetch point name
            if item.patrol_point_master:
                dto.point_name = item.patrol_point_master.nama_titik # Adjusted field name: name -> nama_titik
                
            # Fetch Petugas Name from separate query if NIK is available from session
            if item.patrol_session and item.patrol_session.nik:
                  k = db.query(Karyawan).filter(Karyawan.nik == item.patrol_session.nik).first()
                  if k:
                      dto.nama_petugas = k.nama_karyawan
            
            result.append(dto)
            
        return result
    except Exception as e:
        print(f"Tracking Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# DEPARTMENT TASKS (CLEANING, MAINTENANCE, ETC)
# ==========================================

class DeptTaskSessionDTO(BaseModel):
    id: int
    nik: str
    kode_dept: str
    tanggal: date
    jam_tugas: time
    status: str
    kode_jam_kerja: Optional[str]
    foto_absen: Optional[str]
    lokasi_absen: Optional[str]
    completed_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    

    nama_petugas: Optional[str] = None
    
    class Config:
        from_attributes = True

class DeptTaskPointDTO(BaseModel):
    id: int
    department_task_session_id: int
    department_task_point_master_id: int
    nama_titik: str
    jam: Optional[time]
    lokasi: Optional[str]
    foto: Optional[str]
    keterangan: Optional[str]
    urutan: int
    
    class Config:
        from_attributes = True

class DeptTaskDetailDTO(DeptTaskSessionDTO):
    points: List[DeptTaskPointDTO] = []

class DeptTaskCreateRequest(BaseModel):
    nik: str
    kode_dept: str
    tanggal: date
    jam_tugas: time
    status: Optional[str] = 'active'
    kode_jam_kerja: Optional[str] = None
    foto_absen: Optional[str] = None
    lokasi_absen: Optional[str] = None

@router.get("/tasks", response_model=List[DeptTaskSessionDTO])
async def get_department_tasks(
    kode_dept: str = Query(..., description="Department Code (e.g., UCS, GA)"),
    search: Optional[str] = Query(None, description="Search by NIK/Name"),
    date_start: Optional[date] = Query(None),
    date_end: Optional[date] = Query(None),
    limit: Optional[int] = Query(100),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(DepartmentTaskSessions).outerjoin(Karyawan, DepartmentTaskSessions.nik == Karyawan.nik)
        
        # Filter by Department
        query = query.filter(DepartmentTaskSessions.kode_dept == kode_dept)
        
        if search:
            query = query.filter(
                (DepartmentTaskSessions.nik.like(f"%{search}%")) |
                (Karyawan.nama_karyawan.like(f"%{search}%"))
            )
            
        if date_start:
            query = query.filter(DepartmentTaskSessions.tanggal >= date_start)
            
        if date_end:
            query = query.filter(DepartmentTaskSessions.tanggal <= date_end)
            
        data = query.order_by(desc(DepartmentTaskSessions.created_at)).limit(limit).all()
        
        result = []
        for item in data:
            dto = DeptTaskSessionDTO.from_orm(item)
            karyawan = db.query(Karyawan).filter(Karyawan.nik == item.nik).first()
            if karyawan:
                dto.nama_petugas = karyawan.nama_karyawan
            
            # Format Image URL with Path Construction
            if dto.foto_absen and not dto.foto_absen.startswith(('http', 'https')):
                 date_str = item.tanggal.strftime('%Y%m%d')
                 path = f"uploads/department-task/{item.nik}-{date_str}-absen/{dto.foto_absen}"
                 dto.foto_absen = f"{STORAGE_BASE_URL}{path}"
                 
            result.append(dto)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks", response_model=DeptTaskSessionDTO)
async def create_department_task(request: DeptTaskCreateRequest, db: Session = Depends(get_db)):
    try:
        new_data = DepartmentTaskSessions(
            nik=request.nik,
            kode_dept=request.kode_dept,
            tanggal=request.tanggal,
            jam_tugas=request.jam_tugas,
            status=request.status or 'active',
            kode_jam_kerja=request.kode_jam_kerja,
            foto_absen=request.foto_absen,
            lokasi_absen=request.lokasi_absen,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        
        dto = DeptTaskSessionDTO.from_orm(new_data)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == new_data.nik).first()
        if karyawan:
            dto.nama_petugas = karyawan.nama_karyawan
            
        return dto
    except Exception as e:
        db.rollback()
        print(f"Error Create Task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/tasks/{id}", response_model=DeptTaskSessionDTO)
async def update_department_task(id: int, request: DeptTaskCreateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(DepartmentTaskSessions).filter(DepartmentTaskSessions.id == id).first()
        if not data:
             raise HTTPException(status_code=404, detail="Data Tasks tidak ditemukan")
        
        data.nik = request.nik
        data.kode_dept = request.kode_dept
        data.tanggal = request.tanggal
        data.jam_tugas = request.jam_tugas
        if request.status: data.status = request.status
        if request.kode_jam_kerja: data.kode_jam_kerja = request.kode_jam_kerja
        if request.foto_absen: data.foto_absen = request.foto_absen
        if request.lokasi_absen: data.lokasi_absen = request.lokasi_absen
        data.updated_at = datetime.now()
        
        if request.status == 'complete' and not data.completed_at:
             data.completed_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        
        dto = DeptTaskSessionDTO.from_orm(data)
        karyawan = db.query(Karyawan).filter(Karyawan.nik == data.nik).first()
        if karyawan:
            dto.nama_petugas = karyawan.nama_karyawan
            
        return dto
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/tasks/{id}", response_model=DeptTaskDetailDTO)
async def get_department_task_detail(id: int, db: Session = Depends(get_db)):
    try:
        # Fetch Session
        data = db.query(DepartmentTaskSessions).filter(DepartmentTaskSessions.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Tasks tidak ditemukan")
            
        dto = DeptTaskDetailDTO.from_orm(data)
        
        # Get Officer Name
        karyawan = db.query(Karyawan).filter(Karyawan.nik == data.nik).first()
        if karyawan:
            dto.nama_petugas = karyawan.nama_karyawan
            
        # Get Points
        points_query = db.query(
            DepartmentTaskPoints, 
            DepartmentTaskPointMaster.nama_titik,
            DepartmentTaskPointMaster.urutan
        ).join(
            DepartmentTaskPointMaster, 
            DepartmentTaskPoints.department_task_point_master_id == DepartmentTaskPointMaster.id
        ).filter(
            DepartmentTaskPoints.department_task_session_id == id
        ).order_by(DepartmentTaskPointMaster.urutan).all()
        
        points_list = []
        for p, nama_titik, urutan in points_query:
            point_dto = DeptTaskPointDTO(
                id=p.id,
                department_task_session_id=p.department_task_session_id,
                department_task_point_master_id=p.department_task_point_master_id,
                nama_titik=nama_titik,
                jam=p.jam,
                lokasi=p.lokasi,
                foto=p.foto,
                keterangan=p.keterangan,
                urutan=urutan
            )
            
            # Format Point Image URL
            if point_dto.foto and not point_dto.foto.startswith(('http', 'https')):
                 date_str = data.tanggal.strftime('%Y%m%d')
                 path = f"uploads/department-task/{data.nik}-{date_str}-point/{point_dto.foto}"
                 point_dto.foto = f"{STORAGE_BASE_URL}{path}"
                 
            points_list.append(point_dto)
            
        dto.points = points_list
        
        # Format Session Image URL
        if dto.foto_absen and not dto.foto_absen.startswith(('http', 'https')):
             date_str = data.tanggal.strftime('%Y%m%d')
             path = f"uploads/department-task/{data.nik}-{date_str}-absen/{dto.foto_absen}"
             dto.foto_absen = f"{STORAGE_BASE_URL}{path}"
        
        return dto
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/tasks/{id}")
async def delete_department_task(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(DepartmentTaskSessions).filter(DepartmentTaskSessions.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Tasks tidak ditemukan")
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# TEAMS MONITORING
# ==========================================
from app.routers.master import get_full_image_url

class TeamMemberMonitorDTO(BaseModel):
    nik: str
    nama: str
    foto: Optional[str]
    jabatan: Optional[str] = None
    status_absensi: str
    jam_masuk: Optional[str] = None
    jam_pulang: Optional[str] = None
    foto_masuk: Optional[str] = None
    foto_pulang: Optional[str] = None
    lokasi_masuk: Optional[str] = None

class TeamMonitorGroupDTO(BaseModel):
    schedule_id: int
    kode_jam_kerja: str
    nama_regu: Optional[str]
    jam_mulai: str
    jam_selesai: str
    members: List[TeamMemberMonitorDTO]

@router.get("/teams/monitoring", response_model=List[TeamMonitorGroupDTO])
async def monitor_teams(
    date_filter: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        target_date = date_filter or date.today()
        day_name_map = {
            "Monday": "Senin", "Tuesday": "Selasa", "Wednesday": "Rabu",
            "Thursday": "Kamis", "Friday": "Jumat", "Saturday": "Sabtu", "Sunday": "Minggu"
        }
        day_name = day_name_map[target_date.strftime("%A")]

        schedules = db.query(PatrolSchedules).filter(PatrolSchedules.is_active == 1).all()
        karyawans = db.query(Karyawan).filter(Karyawan.status_aktif_karyawan == '1').all()
        
        overrides_date = db.query(SetJamKerjaByDate).filter(SetJamKerjaByDate.tanggal == target_date).all()
        overrides_date_map = {x.nik: x.kode_jam_kerja for x in overrides_date}
        
        overrides_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.hari == day_name).all()
        overrides_day_map = {x.nik: x.kode_jam_kerja for x in overrides_day}
        
        presensi = db.query(Presensi).filter(Presensi.tanggal == target_date).all()
        presensi_map = {x.nik: x for x in presensi}

        groups_by_code = {}
        for sch in schedules:
            groups_by_code[sch.kode_jam_kerja] = {
                "schedule_id": sch.id,
                "kode_jam_kerja": sch.kode_jam_kerja,
                "nama_regu": sch.name or sch.kode_jam_kerja,
                "jam_mulai": str(sch.start_time),
                "jam_selesai": str(sch.end_time),
                "members": []
            }
            
        for k in karyawans:
            code = overrides_date_map.get(k.nik)
            if not code:
                code = overrides_day_map.get(k.nik)
            if not code:
                code = k.kode_jadwal
                
            if code and code in groups_by_code:
                p = presensi_map.get(k.nik)
                status = "Belum Hadir"
                j_in, j_out, f_in, f_out, l_in = None, None, None, None, None
                
                if p:
                    status = "Hadir"
                    if p.jam_in: j_in = str(p.jam_in)
                    if p.jam_out: j_out = str(p.jam_out)
                    l_in = p.lokasi_in
                    if p.foto_in: 
                         f_in_raw = p.foto_in
                         f_in = get_full_image_url(f_in_raw, "storage/uploads/absensi")
                    if p.foto_out: 
                         f_out_raw = p.foto_out
                         f_out = get_full_image_url(f_out_raw, "storage/uploads/absensi")
                
                k_foto = get_full_image_url(k.foto, "storage/karyawan") if k.foto else None

                member_dto = TeamMemberMonitorDTO(
                    nik=k.nik,
                    nama=k.nama_karyawan,
                    foto=k_foto,
                    jabatan=k.kode_jabatan, 
                    status_absensi=status,
                    jam_masuk=j_in,
                    jam_pulang=j_out,
                    foto_masuk=f_in,
                    foto_pulang=f_out,
                    lokasi_masuk=l_in
                )
                groups_by_code[code]["members"].append(member_dto)

        response_groups = []
        for code, group in groups_by_code.items():
            dto = TeamMonitorGroupDTO(**group)
            response_groups.append(dto)
            
        return response_groups
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
