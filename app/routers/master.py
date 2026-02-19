from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database import get_db
from app.models.models import Karyawan, Departemen, Jabatan, Cabang, StatusKawin, Userkaryawan, PatrolPointMaster, Cuti, PresensiJamkerja, PatrolSchedules, DepartmentTaskPointMaster, SetJamKerjaByDay, SetJamKerjaByDate, PresensiJamkerjaBydateExtra, SetJamKerjaByDate, Users, KaryawanWajah
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, validator
from datetime import date, datetime, time
import os
import shutil
import uuid
from pathlib import Path
from fastapi import File, UploadFile, Form
from app.core.security import get_password_hash
from app.core.permissions import CurrentUser, get_current_user, require_permission_dependency

router = APIRouter(
    prefix="/api/master",
    tags=["Master Data"]
)

# Get BASE_URL from environment
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

def get_full_image_url(path: Optional[str], folder: str = "storage/karyawan") -> Optional[str]:
    """Convert relative image path to full URL"""
    if not path:
        return None
    # If already a full URL, return as is
    if path.startswith(('http://', 'https://')):
        return path
    # If path already starts with storage/, use as is
    if path.startswith('storage/'):
        return f"{BASE_URL}/{path}"
    # Otherwise, prepend folder path
    return f"{BASE_URL}/{folder}/{path}"

class KaryawanDTO(BaseModel):
    nik: str
    nama_karyawan: str
    no_hp: Optional[str]
    foto: Optional[str]
    status_aktif_karyawan: str
    nama_dept: Optional[str]
    nama_jabatan: Optional[str]
    nama_cabang: Optional[str]
    
    kode_cabang: Optional[str] = None
    kode_dept: Optional[str] = None
    kode_jabatan: Optional[str] = None
    kode_status_kawin: Optional[str] = None
    jenis_kelamin: Optional[str] = None
    status_karyawan: Optional[str] = None
    tempat_lahir: Optional[str] = None
    tanggal_lahir: Optional[date] = None
    alamat: Optional[str] = None
    
    # New Extended Fields
    no_ktp: str
    tanggal_masuk: Optional[date]
    no_kartu_anggota: Optional[str]
    masa_aktif_kartu_anggota: Optional[date]
    keterangan_status_kawin: Optional[str]
    pendidikan_terakhir: Optional[str]
    no_ijazah: Optional[str]
    kontak_darurat_nama: Optional[str]
    kontak_darurat_hp: Optional[str]
    kontak_darurat_alamat: Optional[str]
    lock_location: str
    lock_jam_kerja: str
    lock_device_login: str
    allow_multi_device: str
    pin: Optional[int]
    foto_ktp: Optional[str]
    foto_kartu_anggota: Optional[str]
    foto_ijazah: Optional[str]
    no_sim: Optional[str]
    kode_jadwal: Optional[str]

    id_user: Optional[int]
    sisa_hari_anggota: Optional[int]
    
class PaginationMeta(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    per_page: int

class KaryawanListResponse(BaseModel):
    status: bool
    data: List[KaryawanDTO]
    meta: Optional[PaginationMeta] = None

class OptionItem(BaseModel):
    code: str
    name: str

class MasterOptionsResponse(BaseModel):
    departemen: List[OptionItem]
    jabatan: List[OptionItem]
    cabang: List[OptionItem]
    status_kawin: List[OptionItem]
    jadwal: List[OptionItem]

class DepartemenDTO(BaseModel):
    kode_dept: str
    nama_dept: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        orm_mode = True

class DepartemenCreateRequest(BaseModel):
    kode_dept: str
    nama_dept: str

class JabatanDTO(BaseModel):
    kode_jabatan: str
    nama_jabatan: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        orm_mode = True

class JabatanCreateRequest(BaseModel):
    kode_jabatan: str
    nama_jabatan: str

class CabangDTO(BaseModel):
    kode_cabang: str
    nama_cabang: str
    alamat_cabang: str
    telepon_cabang: str
    lokasi_cabang: str
    radius_cabang: int
    kode_up3: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        orm_mode = True

class CabangCreateRequest(BaseModel):
    kode_cabang: str
    nama_cabang: str
    alamat_cabang: str
    telepon_cabang: str
    lokasi_cabang: str
    radius_cabang: int
    kode_up3: Optional[str] = None

@router.get("/departemen", response_model=List[DepartemenDTO])
async def get_departemen_list(db: Session = Depends(get_db)):
    try:
        data = db.query(Departemen).order_by(Departemen.kode_dept).all()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/departemen", response_model=DepartemenDTO)
async def create_departemen(request: DepartemenCreateRequest, db: Session = Depends(get_db)):
    try:
        # Check if exists
        existing = db.query(Departemen).filter(Departemen.kode_dept == request.kode_dept).first()
        if existing:
            raise HTTPException(status_code=400, detail="Kode Departemen sudah ada")

        new_dept = Departemen(
            kode_dept=request.kode_dept,
            nama_dept=request.nama_dept,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_dept)
        db.commit()
        db.refresh(new_dept)
        return new_dept
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error Create Dept: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/departemen/{kode_dept}", response_model=DepartemenDTO)
async def update_departemen(kode_dept: str, request: DepartemenCreateRequest, db: Session = Depends(get_db)):
    try:
        dept = db.query(Departemen).filter(Departemen.kode_dept == kode_dept).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Departemen tidak ditemukan")
        
        dept.kode_dept = request.kode_dept
        dept.nama_dept = request.nama_dept
        dept.updated_at = datetime.now()
        
        db.commit()
        db.refresh(dept)
        return dept
    except Exception as e:
        db.rollback()
        print(f"Error Update Dept: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/departemen/{kode_dept}")
async def delete_departemen(kode_dept: str, db: Session = Depends(get_db)):
    try:
        dept = db.query(Departemen).filter(Departemen.kode_dept == kode_dept).first()
        if not dept:
            raise HTTPException(status_code=404, detail="Departemen tidak ditemukan")
        
        db.delete(dept)
        db.commit()
        return {"status": True, "message": "Departemen berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Dept: {str(e)}")
        if "Foreign key constraint" in str(e) or "foreign key constraint" in str(e):
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karena ada data terkait (Karyawan/Lainnya)")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MASTER JABATAN
# ==========================================

@router.get("/jabatan", response_model=List[JabatanDTO])
async def get_jabatan_list(
    current_user: CurrentUser = Depends(require_permission_dependency("jabatan.index")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Jabatan).order_by(Jabatan.kode_jabatan).all()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jabatan", response_model=JabatanDTO)
async def create_jabatan(
    request: JabatanCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("jabatan.create")),
    db: Session = Depends(get_db)
):
    try:
        # Check if exists
        existing = db.query(Jabatan).filter(Jabatan.kode_jabatan == request.kode_jabatan).first()
        if existing:
            raise HTTPException(status_code=400, detail="Kode Jabatan sudah ada")

        new_data = Jabatan(
            kode_jabatan=request.kode_jabatan,
            nama_jabatan=request.nama_jabatan,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        return new_data
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error Create Jabatan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/jabatan/{kode_jabatan}", response_model=JabatanDTO)
async def update_jabatan(
    kode_jabatan: str,
    request: JabatanCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("jabatan.update")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Jabatan).filter(Jabatan.kode_jabatan == kode_jabatan).first()
        if not data:
            raise HTTPException(status_code=404, detail="Jabatan tidak ditemukan")
        
        data.kode_jabatan = request.kode_jabatan
        data.nama_jabatan = request.nama_jabatan
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        return data
    except Exception as e:
        db.rollback()
        print(f"Error Update Jabatan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/jabatan/{kode_jabatan}")
async def delete_jabatan(
    kode_jabatan: str,
    current_user: CurrentUser = Depends(require_permission_dependency("jabatan.delete")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Jabatan).filter(Jabatan.kode_jabatan == kode_jabatan).first()
        if not data:
            raise HTTPException(status_code=404, detail="Jabatan tidak ditemukan")
        
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Jabatan berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Jabatan: {str(e)}")
        if "Foreign key constraint" in str(e) or "foreign key constraint" in str(e):
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karena ada data terkait")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# MASTER CABANG
# ==========================================

@router.get("/karyawan/options")
async def get_karyawan_options(db: Session = Depends(get_db)):
    try:
        data = db.query(Karyawan).order_by(Karyawan.nama_karyawan).all()
        return [{"nik": k.nik, "nama_karyawan": k.nama_karyawan} for k in data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cabang/options")
async def get_cabang_options(db: Session = Depends(get_db)):
    try:
        data = db.query(Cabang).order_by(Cabang.kode_cabang).all()
        return [{"kode_cabang": c.kode_cabang, "nama_cabang": c.nama_cabang} for c in data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/departemen/options")
async def get_departemen_options(db: Session = Depends(get_db)):
    try:
        data = db.query(Departemen).order_by(Departemen.kode_dept).all()
        return [{"kode_dept": d.kode_dept, "nama_dept": d.nama_dept} for d in data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cabang", response_model=List[CabangDTO])
async def get_cabang_list(
    current_user: CurrentUser = Depends(require_permission_dependency("cabang.index")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Cabang).order_by(Cabang.kode_cabang).all()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cabang", response_model=CabangDTO)
async def create_cabang(
    request: CabangCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("cabang.create")),
    db: Session = Depends(get_db)
):
    try:
        # Check if exists
        existing = db.query(Cabang).filter(Cabang.kode_cabang == request.kode_cabang).first()
        if existing:
            raise HTTPException(status_code=400, detail="Kode Cabang sudah ada")

        new_data = Cabang(
            kode_cabang=request.kode_cabang,
            nama_cabang=request.nama_cabang,
            alamat_cabang=request.alamat_cabang,
            telepon_cabang=request.telepon_cabang,
            lokasi_cabang=request.lokasi_cabang,
            radius_cabang=request.radius_cabang,
            kode_up3=request.kode_up3,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        return new_data
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error Create Cabang: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/cabang/{kode_cabang}", response_model=CabangDTO)
async def update_cabang(
    kode_cabang: str,
    request: CabangCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("cabang.update")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Cabang).filter(Cabang.kode_cabang == kode_cabang).first()
        if not data:
            raise HTTPException(status_code=404, detail="Cabang tidak ditemukan")
        
        data.kode_cabang = request.kode_cabang
        data.nama_cabang = request.nama_cabang
        data.alamat_cabang = request.alamat_cabang
        data.telepon_cabang = request.telepon_cabang
        data.lokasi_cabang = request.lokasi_cabang
        data.radius_cabang = request.radius_cabang
        data.kode_up3 = request.kode_up3
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        return data
    except Exception as e:
        db.rollback()
        print(f"Error Update Cabang: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cabang/{kode_cabang}")
async def delete_cabang(
    kode_cabang: str,
    current_user: CurrentUser = Depends(require_permission_dependency("cabang.delete")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Cabang).filter(Cabang.kode_cabang == kode_cabang).first()
        if not data:
            raise HTTPException(status_code=404, detail="Cabang tidak ditemukan")
        
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Cabang berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Cabang: {str(e)}")
        if "Foreign key constraint" in str(e) or "foreign key constraint" in str(e):
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karena ada data terkait")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# MASTER PATROL POINTS
# ==========================================

class PatrolPointDTO(BaseModel):
    id: int
    kode_cabang: str
    nama_titik: str
    latitude: float
    longitude: float
    radius: int
    urutan: Optional[int]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class PatrolPointCreateRequest(BaseModel):
    kode_cabang: str
    nama_titik: str
    latitude: float
    longitude: float
    radius: int = 30
    urutan: int = 0

@router.get("/patrol-points", response_model=List[PatrolPointDTO])
async def get_patrol_points(
    kode_cabang: Optional[str] = Query(None, description="Filter Kode Cabang"),
    search: Optional[str] = Query(None, description="Search Nama Titik"),
    current_user: CurrentUser = Depends(require_permission_dependency("patrolpoint.index")),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(PatrolPointMaster)
        
        if kode_cabang:
            query = query.filter(PatrolPointMaster.kode_cabang == kode_cabang)
        if search:
            query = query.filter(PatrolPointMaster.nama_titik.like(f"%{search}%"))
            
        return query.order_by(PatrolPointMaster.nama_titik).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/patrol-points", response_model=PatrolPointDTO)
async def create_patrol_point(
    request: PatrolPointCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("patrolpoint.create")),
    db: Session = Depends(get_db)
):
    try:
        new_point = PatrolPointMaster(
            kode_cabang=request.kode_cabang,
            nama_titik=request.nama_titik,
            latitude=request.latitude,
            longitude=request.longitude,
            radius=request.radius,
            urutan=request.urutan,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_point)
        db.commit()
        db.refresh(new_point)
        return new_point
    except Exception as e:
        db.rollback()
        print(f"Error Create Patrol Point: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/patrol-points/{id}", response_model=PatrolPointDTO)
async def update_patrol_point(
    id: int,
    request: PatrolPointCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("patrolpoint.update")),
    db: Session = Depends(get_db)
):
    try:
        point = db.query(PatrolPointMaster).filter(PatrolPointMaster.id == id).first()
        if not point:
            raise HTTPException(status_code=404, detail="Patrol Point tidak ditemukan")
        
        point.kode_cabang = request.kode_cabang
        point.nama_titik = request.nama_titik
        point.latitude = request.latitude
        point.longitude = request.longitude
        point.radius = request.radius
        point.urutan = request.urutan
        point.updated_at = datetime.now()
        
        db.commit()
        db.refresh(point)
        return point
    except Exception as e:
        db.rollback()
        print(f"Error Update Patrol Point: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/patrol-points/{id}")
async def delete_patrol_point(
    id: int,
    current_user: CurrentUser = Depends(require_permission_dependency("patrolpoint.delete")),
    db: Session = Depends(get_db)
):
    try:
        point = db.query(PatrolPointMaster).filter(PatrolPointMaster.id == id).first()
        if not point:
            raise HTTPException(status_code=404, detail="Patrol Point tidak ditemukan")
        
        db.delete(point)
        db.commit()
        return {"status": True, "message": "Patrol Point berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Patrol Point: {str(e)}")
        if "Foreign key constraint" in str(e) or "foreign key constraint" in str(e):
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karena ada data terkait")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MASTER CUTI
# ==========================================

class CutiDTO(BaseModel):
    kode_cuti: str
    jenis_cuti: str
    jumlah_hari: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class CutiCreateRequest(BaseModel):
    kode_cuti: str
    jenis_cuti: str
    jumlah_hari: int

@router.get("/cuti", response_model=List[CutiDTO])
async def get_cuti_list(
    current_user: CurrentUser = Depends(require_permission_dependency("cuti.index")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Cuti).order_by(Cuti.kode_cuti).all()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cuti", response_model=CutiDTO)
async def create_cuti(
    request: CutiCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("cuti.create")),
    db: Session = Depends(get_db)
):
    try:
        existing = db.query(Cuti).filter(Cuti.kode_cuti == request.kode_cuti).first()
        if existing:
            raise HTTPException(status_code=400, detail="Kode Cuti sudah ada")

        new_data = Cuti(
            kode_cuti=request.kode_cuti,
            jenis_cuti=request.jenis_cuti,
            jumlah_hari=request.jumlah_hari,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        return new_data
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error Create Cuti: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/cuti/{kode_cuti}", response_model=CutiDTO)
async def update_cuti(
    kode_cuti: str,
    request: CutiCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("cuti.update")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Cuti).filter(Cuti.kode_cuti == kode_cuti).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Cuti tidak ditemukan")
        
        data.kode_cuti = request.kode_cuti
        data.jenis_cuti = request.jenis_cuti
        data.jumlah_hari = request.jumlah_hari
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        return data
    except Exception as e:
        db.rollback()
        print(f"Error Update Cuti: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cuti/{kode_cuti}")
async def delete_cuti(
    kode_cuti: str,
    current_user: CurrentUser = Depends(require_permission_dependency("cuti.delete")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(Cuti).filter(Cuti.kode_cuti == kode_cuti).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Cuti tidak ditemukan")
        
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data Cuti berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Cuti: {str(e)}")
        if "Foreign key constraint" in str(e) or "foreign key constraint" in str(e):
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karena ada data terkait")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MASTER JAM KERJA
# ==========================================

class JamKerjaDTO(BaseModel):
    kode_jam_kerja: str
    nama_jam_kerja: str
    jam_masuk: Optional[time]
    jam_pulang: Optional[time]
    istirahat: str
    total_jam: int
    lintashari: str
    jam_awal_istirahat: Optional[time] = None
    jam_akhir_istirahat: Optional[time] = None
    keterangan: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class JamKerjaCreateRequest(BaseModel):
    kode_jam_kerja: str
    nama_jam_kerja: str
    jam_masuk: Any
    jam_pulang: Any
    istirahat: str
    total_jam: int
    lintashari: str
    jam_awal_istirahat: Optional[Any] = None
    jam_akhir_istirahat: Optional[Any] = None
    keterangan: Optional[str] = None

    @validator('jam_masuk', 'jam_pulang', 'jam_awal_istirahat', 'jam_akhir_istirahat', pre=True)
    def parse_time(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                # Try parsing with seconds or without
                if len(v.split(':')) == 2:
                    return datetime.strptime(v, '%H:%M').time()
                return datetime.strptime(v, '%H:%M:%S').time()
            except ValueError:
                return v # Let native validation fail or handle it
        return v

@router.get("/jamkerja", response_model=List[JamKerjaDTO])
async def get_jamkerja_list(
    current_user: CurrentUser = Depends(require_permission_dependency("jamkerja.index")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(PresensiJamkerja).order_by(PresensiJamkerja.kode_jam_kerja).all()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jamkerja", response_model=JamKerjaDTO)
async def create_jamkerja(
    request: JamKerjaCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("jamkerja.create")),
    db: Session = Depends(get_db)
):
    try:
        existing = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == request.kode_jam_kerja).first()
        if existing:
            raise HTTPException(status_code=400, detail="Kode Jam Kerja sudah ada")

        # Convert simple types manually if needed, but Pydantic conversion handles string to time well mostly.
        # However, for SQLAlchemy Time column, usually creating object with time() object is best.
        # The validator handles string to time.
        
        # Pydantic validates input string to time object for the model fields? 
        # Actually CreateRequest defined fields as str to accept user input easily, 
        # but we need to convert to time objects for SQLAlchemy.
        
        # Helper parse
        def to_time(val):
            if not val: return None
            if isinstance(val, str):
                 if len(val.split(':')) == 2:
                    return datetime.strptime(val, '%H:%M').time()
                 return datetime.strptime(val, '%H:%M:%S').time()
            return val

        new_data = PresensiJamkerja(
            kode_jam_kerja=request.kode_jam_kerja,
            nama_jam_kerja=request.nama_jam_kerja,
            jam_masuk=to_time(request.jam_masuk),
            jam_pulang=to_time(request.jam_pulang),
            istirahat=request.istirahat,
            total_jam=request.total_jam,
            lintashari=request.lintashari,
            jam_awal_istirahat=to_time(request.jam_awal_istirahat),
            jam_akhir_istirahat=to_time(request.jam_akhir_istirahat),
            keterangan=request.keterangan,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        return new_data
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error Create Jam Kerja: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/jamkerja/{kode}", response_model=JamKerjaDTO)
async def update_jamkerja(
    kode: str,
    request: JamKerjaCreateRequest,
    current_user: CurrentUser = Depends(require_permission_dependency("jamkerja.update")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == kode).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Jam Kerja tidak ditemukan")
        
        def to_time(val):
            if not val: return None
            if isinstance(val, str):
                 if len(val.split(':')) == 2:
                    return datetime.strptime(val, '%H:%M').time()
                 return datetime.strptime(val, '%H:%M:%S').time()
            return val

        data.kode_jam_kerja = request.kode_jam_kerja # If allowed to change PK? Ideally risky but let's assume allowed if cascade works or if user careful.
        # Actually usually changing PK is bad practice. But requested "update". Let's stick with updating fields.
        # If kode_jam_kerja changes, we might have issues if it's FK elsewhere.
        # But let's allow updating non-PK fields primarily.
        
        # If user really wants to change kode, that's complex. Let's assume kode shouldn't change or handle it carefully.
        # For simplicity, let's update fields.
        if kode != request.kode_jam_kerja:
             # Check collision
             existing = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == request.kode_jam_kerja).first()
             if existing:
                 raise HTTPException(status_code=400, detail="Kode Jam Kerja baru sudah digunakan")
             data.kode_jam_kerja = request.kode_jam_kerja

        data.nama_jam_kerja = request.nama_jam_kerja
        data.jam_masuk = to_time(request.jam_masuk)
        data.jam_pulang = to_time(request.jam_pulang)
        data.istirahat = request.istirahat
        data.total_jam = request.total_jam
        data.lintashari = request.lintashari
        data.jam_awal_istirahat = to_time(request.jam_awal_istirahat)
        data.jam_akhir_istirahat = to_time(request.jam_akhir_istirahat)
        data.keterangan = request.keterangan
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        return data
    except Exception as e:
        db.rollback()
        print(f"Error Update Jam Kerja: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/jamkerja/{kode}")
async def delete_jamkerja(
    kode: str,
    current_user: CurrentUser = Depends(require_permission_dependency("jamkerja.delete")),
    db: Session = Depends(get_db)
):
    try:
        data = db.query(PresensiJamkerja).filter(PresensiJamkerja.kode_jam_kerja == kode).first()
        if not data:
            raise HTTPException(status_code=404, detail="Data Jam Kerja tidak ditemukan")
        
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Data Jam Kerja berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Jam Kerja: {str(e)}")
        if "Foreign key constraint" in str(e) or "foreign key constraint" in str(e):
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karena ada data terkait")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MASTER PATROL SCHEDULE (JADWAL TUGAS)
# ==========================================

class PatrolScheduleDTO(BaseModel):
    id: int
    kode_jam_kerja: str
    start_time: time
    end_time: time
    kode_dept: Optional[str]
    kode_cabang: Optional[str]
    is_active: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class PatrolScheduleCreateRequest(BaseModel):
    kode_jam_kerja: str
    start_time: str
    end_time: str
    kode_dept: Optional[str] = None
    kode_cabang: Optional[str] = None
    is_active: int = 1

    @validator('start_time', 'end_time', pre=True)
    def parse_time(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                if len(v.split(':')) == 2:
                    return datetime.strptime(v, '%H:%M').time()
                return datetime.strptime(v, '%H:%M:%S').time()
            except ValueError:
                return v
        return v

@router.get("/patrol-schedules", response_model=List[PatrolScheduleDTO])
async def get_patrol_schedules(
    kode_cabang: Optional[str] = Query(None, description="Filter Kode Cabang"),
     kode_dept: Optional[str] = Query(None, description="Filter Kode Dept"),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(PatrolSchedules)
        
        if kode_cabang:
             query = query.filter(PatrolSchedules.kode_cabang == kode_cabang)
        if kode_dept:
             query = query.filter(PatrolSchedules.kode_dept == kode_dept)
            
        return query.order_by(PatrolSchedules.kode_jam_kerja, PatrolSchedules.start_time).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/patrol-schedules", response_model=PatrolScheduleDTO)
async def create_patrol_schedule(request: PatrolScheduleCreateRequest, db: Session = Depends(get_db)):
    try:
        def to_time(val):
            if not val: return None
            if isinstance(val, str):
                 if len(val.split(':')) == 2:
                    return datetime.strptime(val, '%H:%M').time()
                 return datetime.strptime(val, '%H:%M:%S').time()
            return val

        new_data = PatrolSchedules(
            kode_jam_kerja=request.kode_jam_kerja,
            start_time=to_time(request.start_time),
            end_time=to_time(request.end_time),
            kode_dept=request.kode_dept,
            kode_cabang=request.kode_cabang,
            is_active=request.is_active,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_data)
        db.commit()
        db.refresh(new_data)
        return new_data
    except Exception as e:
        db.rollback()
        print(f"Error Create Patrol Schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/patrol-schedules/{id}", response_model=PatrolScheduleDTO)
async def update_patrol_schedule(id: int, request: PatrolScheduleCreateRequest, db: Session = Depends(get_db)):
    try:
        data = db.query(PatrolSchedules).filter(PatrolSchedules.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Patrol Schedule tidak ditemukan")
        
        def to_time(val):
            if not val: return None
            if isinstance(val, str):
                 if len(val.split(':')) == 2:
                    return datetime.strptime(val, '%H:%M').time()
                 return datetime.strptime(val, '%H:%M:%S').time()
            return val

        data.kode_jam_kerja = request.kode_jam_kerja
        data.start_time = to_time(request.start_time)
        data.end_time = to_time(request.end_time)
        data.kode_dept = request.kode_dept
        data.kode_cabang = request.kode_cabang
        data.is_active = request.is_active
        data.updated_at = datetime.now()
        
        db.commit()
        db.refresh(data)
        return data
    except Exception as e:
        db.rollback()
        print(f"Error Update Patrol Schedule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/patrol-schedules/{id}")
async def delete_patrol_schedule(id: int, db: Session = Depends(get_db)):
    try:
        data = db.query(PatrolSchedules).filter(PatrolSchedules.id == id).first()
        if not data:
            raise HTTPException(status_code=404, detail="Patrol Schedule tidak ditemukan")
        
        db.delete(data)
        db.commit()
        return {"status": True, "message": "Patrol Schedule berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Patrol Schedule: {str(e)}")
        if "Foreign key constraint" in str(e) or "foreign key constraint" in str(e):
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karena ada data terkait")
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MASTER DEPARTMENT TASK POINT (TITIK TUGAS DEPARTMENT)
# ==========================================

class DeptTaskPointDTO(BaseModel):
    id: int
    kode_cabang: str
    kode_dept: str
    nama_titik: str
    urutan: int
    radius: int
    is_active: int
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

class DeptTaskPointCreateRequest(BaseModel):
    kode_cabang: str
    kode_dept: str
    nama_titik: str
    urutan: int = 1
    radius: int = 30
    is_active: int = 1
    latitude: Optional[float] = None
    longitude: Optional[float] = None

@router.get("/dept-task-points", response_model=List[DeptTaskPointDTO])
async def get_dept_task_points(
    kode_cabang: Optional[str] = Query(None, description="Filter Kode Cabang"),
    kode_dept: Optional[str] = Query(None, description="Filter Kode Dept"),
    search: Optional[str] = Query(None, description="Search Nama Titik"),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(DepartmentTaskPointMaster)
        
        if kode_cabang:
            query = query.filter(DepartmentTaskPointMaster.kode_cabang == kode_cabang)
        if kode_dept:
            query = query.filter(DepartmentTaskPointMaster.kode_dept == kode_dept)
        if search:
            query = query.filter(DepartmentTaskPointMaster.nama_titik.like(f"%{search}%"))
            
        return query.order_by(DepartmentTaskPointMaster.kode_dept, DepartmentTaskPointMaster.urutan).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/dept-task-points", response_model=DeptTaskPointDTO)
async def create_dept_task_point(request: DeptTaskPointCreateRequest, db: Session = Depends(get_db)):
    try:
        new_point = DepartmentTaskPointMaster(
            kode_cabang=request.kode_cabang,
            kode_dept=request.kode_dept,
            nama_titik=request.nama_titik,
            urutan=request.urutan,
            radius=request.radius,
            is_active=request.is_active,
            latitude=request.latitude,
            longitude=request.longitude,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_point)
        db.commit()
        db.refresh(new_point)
        return new_point
    except Exception as e:
        db.rollback()
        print(f"Error Create Dept Task Point: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/dept-task-points/{id}", response_model=DeptTaskPointDTO)
async def update_dept_task_point(id: int, request: DeptTaskPointCreateRequest, db: Session = Depends(get_db)):
    try:
        point = db.query(DepartmentTaskPointMaster).filter(DepartmentTaskPointMaster.id == id).first()
        if not point:
            raise HTTPException(status_code=404, detail="Department Task Point tidak ditemukan")
        
        point.kode_cabang = request.kode_cabang
        point.kode_dept = request.kode_dept
        point.nama_titik = request.nama_titik
        point.urutan = request.urutan
        point.radius = request.radius
        point.is_active = request.is_active
        point.latitude = request.latitude
        point.longitude = request.longitude
        point.updated_at = datetime.now()
        
        db.commit()
        db.refresh(point)
        return point
    except Exception as e:
        db.rollback()
        print(f"Error Update Dept Task Point: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/dept-task-points/{id}")
async def delete_dept_task_point(id: int, db: Session = Depends(get_db)):
    try:
        point = db.query(DepartmentTaskPointMaster).filter(DepartmentTaskPointMaster.id == id).first()
        if not point:
            raise HTTPException(status_code=404, detail="Department Task Point tidak ditemukan")
        
        db.delete(point)
        db.commit()
        return {"status": True, "message": "Department Task Point berhasil dihapus"}
    except Exception as e:
        db.rollback()
        print(f"Error Delete Dept Task Point: {str(e)}")
        if "Foreign key constraint" in str(e) or "foreign key constraint" in str(e):
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karena ada data terkait")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/options", response_model=MasterOptionsResponse)
async def get_master_options(db: Session = Depends(get_db)):
    try:
        dept = db.query(Departemen).order_by(Departemen.kode_dept).all()
        jab = db.query(Jabatan).order_by(Jabatan.kode_jabatan).all()
        cab = db.query(Cabang).order_by(Cabang.kode_cabang).all()
        kawin = db.query(StatusKawin).order_by(StatusKawin.kode_status_kawin).all()
        jadwal = db.query(PresensiJamkerja).order_by(PresensiJamkerja.kode_jam_kerja).all()
        
        return MasterOptionsResponse(
            departemen=[OptionItem(code=d.kode_dept, name=d.nama_dept) for d in dept],
            jabatan=[OptionItem(code=j.kode_jabatan, name=j.nama_jabatan) for j in jab],
            cabang=[OptionItem(code=c.kode_cabang, name=c.nama_cabang) for c in cab],
            status_kawin=[OptionItem(code=k.kode_status_kawin, name=k.status_kawin) for k in kawin],
            jadwal=[OptionItem(code=j.kode_jam_kerja, name=j.nama_jam_kerja) for j in jadwal]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/karyawan", response_model=KaryawanListResponse)
async def get_karyawan_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=10000),
    search: Optional[str] = None,
    dept_code: Optional[str] = None,
    cabang_code: Optional[str] = None,
    masa_anggota: Optional[str] = Query(None, description="aktif, expiring, expired"),
    current_user: CurrentUser = Depends(require_permission_dependency("karyawan.index")),
    db: Session = Depends(get_db)
):
    try:
        # Define calculated column
        sisa_hari_col = func.datediff(Karyawan.masa_aktif_kartu_anggota, func.current_date())

        query = db.query(
            Karyawan.nik,
            Karyawan.nama_karyawan,
            Karyawan.no_hp,
            Karyawan.foto,
            Karyawan.status_aktif_karyawan,
            Karyawan.no_ktp,
            Karyawan.tanggal_masuk,
            Karyawan.no_kartu_anggota,
            Karyawan.masa_aktif_kartu_anggota,
            Karyawan.pendidikan_terakhir,
            Karyawan.no_ijazah,
            Karyawan.kontak_darurat_nama,
            Karyawan.kontak_darurat_hp,
            Karyawan.kontak_darurat_alamat,
            Karyawan.lock_location,
            Karyawan.lock_jam_kerja,
            Karyawan.lock_device_login,
            Karyawan.allow_multi_device,
            Karyawan.pin,
            Karyawan.foto_ktp,
            Karyawan.foto_kartu_anggota,
            Karyawan.foto_ijazah,
            Karyawan.no_sim,
            Karyawan.kode_jadwal,
            Karyawan.masa_aktif_kartu_anggota,
            
            Departemen.nama_dept,
            Jabatan.nama_jabatan,
            Cabang.nama_cabang,
            StatusKawin.status_kawin.label("keterangan_status_kawin"),
            Userkaryawan.id_user,
            sisa_hari_col.label("sisa_hari_anggota")
        ).outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
         .outerjoin(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
         .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
         .outerjoin(StatusKawin, Karyawan.kode_status_kawin == StatusKawin.kode_status_kawin)\
         .outerjoin(Userkaryawan, Karyawan.nik == Userkaryawan.nik)

        # Filters
        if search:
            search_query = f"%{search}%"
            query = query.filter(
                (Karyawan.nama_karyawan.like(search_query)) | 
                (Karyawan.nik.like(search_query))
            )
            
        if dept_code:
            query = query.filter(Karyawan.kode_dept == dept_code)
            
        if cabang_code:
            query = query.filter(Karyawan.kode_cabang == cabang_code)
            
        if masa_anggota:
            if masa_anggota == 'aktif':
                query = query.filter(sisa_hari_col >= 0)
            elif masa_anggota == 'expiring':
                query = query.filter(sisa_hari_col.between(0, 30))
            elif masa_anggota == 'expired':
                query = query.filter(sisa_hari_col < 0)

        # Count total
        total_items = query.count()
        import math
        total_pages = math.ceil(total_items / per_page)
        
        # Pagination
        query = query.order_by(Karyawan.nama_karyawan.asc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        
        results = query.all()
        
        data_list = []
        for row in results:
            data_list.append(KaryawanDTO(
                nik=row.nik,
                nama_karyawan=row.nama_karyawan,
                no_hp=row.no_hp,
                foto=get_full_image_url(row.foto),
                status_aktif_karyawan=row.status_aktif_karyawan,
                nama_dept=row.nama_dept or "-",
                nama_jabatan=row.nama_jabatan or "-",
                nama_cabang=row.nama_cabang or "-",
                
                # New Fields
                no_ktp=row.no_ktp,
                tanggal_masuk=row.tanggal_masuk,
                no_kartu_anggota=row.no_kartu_anggota,
                masa_aktif_kartu_anggota=row.masa_aktif_kartu_anggota,
                keterangan_status_kawin=row.keterangan_status_kawin,
                pendidikan_terakhir=row.pendidikan_terakhir,
                no_ijazah=row.no_ijazah,
                kontak_darurat_nama=row.kontak_darurat_nama,
                kontak_darurat_hp=row.kontak_darurat_hp,
                kontak_darurat_alamat=row.kontak_darurat_alamat,
                lock_location=row.lock_location,
                lock_jam_kerja=row.lock_jam_kerja,
                lock_device_login=row.lock_device_login,
                allow_multi_device=row.allow_multi_device,
                pin=row.pin,
                foto_ktp=get_full_image_url(row.foto_ktp),
                foto_kartu_anggota=get_full_image_url(row.foto_kartu_anggota),
                foto_ijazah=get_full_image_url(row.foto_ijazah),
                no_sim=row.no_sim,
                kode_jadwal=row.kode_jadwal,


                id_user=row.id_user,
                sisa_hari_anggota=row.sisa_hari_anggota
            ))
            
        return KaryawanListResponse(
            status=True,
            data=data_list,
            meta=PaginationMeta(
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                per_page=per_page
            )
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# MASTER KARYAWAN CRUD
# ==========================================

def save_upload(file_obj: UploadFile, subfolder: str = "") -> str:
    if not file_obj or not file_obj.filename: return None
    try:
        base_dir = "/var/www/appPatrol/storage/app/public/karyawan"
        target_dir = os.path.join(base_dir, subfolder)
        os.makedirs(target_dir, exist_ok=True)
        
        ext = os.path.splitext(file_obj.filename)[1]
        unique_name = f"{uuid.uuid4()}{ext}"
        target_path = os.path.join(target_dir, unique_name)
        
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file_obj.file, buffer)
            
        return unique_name
    except Exception as e:
        print(f"Failed to save file: {e}")
        return None

@router.post("/karyawan")
async def create_karyawan(
    nik: str = Form(...),
    nama_karyawan: str = Form(...),
    no_ktp: str = Form(...),
    jenis_kelamin: str = Form(...),
    kode_cabang: str = Form(...),
    kode_dept: str = Form(...),
    kode_jabatan: str = Form(...),
    tanggal_masuk: date = Form(...),
    status_karyawan: str = Form('C'), # C=Contract, P=Permanent
    status_aktif_karyawan: str = Form('1'),
    # password removed, default 12345
    
    # Optional Fields
    tempat_lahir: Optional[str] = Form(None),
    tanggal_lahir: Optional[date] = Form(None),
    alamat: Optional[str] = Form(None),
    no_hp: Optional[str] = Form(None),
    kontak_darurat_nama: Optional[str] = Form(None),
    kontak_darurat_hp: Optional[str] = Form(None),
    kontak_darurat_alamat: Optional[str] = Form(None),
    kode_status_kawin: Optional[str] = Form(None),
    pendidikan_terakhir: Optional[str] = Form(None),
    no_ijazah: Optional[str] = Form(None),
    no_sim: Optional[str] = Form(None),
    no_kartu_anggota: Optional[str] = Form(None),
    masa_aktif_kartu_anggota: Optional[date] = Form(None),
    kode_jadwal: Optional[str] = Form(None),
    pin: Optional[int] = Form(None),
    
    # Settings settings
    lock_location: str = Form('1'),
    lock_device_login: str = Form('0'),
    allow_multi_device: str = Form('0'),
    lock_jam_kerja: str = Form('1'),
    lock_patrol: str = Form('1'),
    
    # Files
    foto: UploadFile = File(None),
    foto_ktp: UploadFile = File(None),
    foto_kartu_anggota: UploadFile = File(None),
    foto_ijazah: UploadFile = File(None),
    foto_sim: UploadFile = File(None),
    
    current_user: CurrentUser = Depends(require_permission_dependency("karyawan.create")),
    db: Session = Depends(get_db)
):
    try:
        existing = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if existing:
            raise HTTPException(status_code=400, detail="NIK Karyawan sudah ada")
            
        # Save files
        foto_path = save_upload(foto, "")
        foto_ktp_path = save_upload(foto_ktp, "ktp")
        foto_ka_path = save_upload(foto_kartu_anggota, "kartu")
        foto_ijazah_path = save_upload(foto_ijazah, "ijazah")
        foto_sim_path = save_upload(foto_sim, "sim")
        
        new_karyawan = Karyawan(
            nik=nik,
            nama_karyawan=nama_karyawan,
            no_ktp=no_ktp,
            jenis_kelamin=jenis_kelamin,
            kode_cabang=kode_cabang,
            kode_dept=kode_dept,
            kode_jabatan=kode_jabatan,
            tanggal_masuk=tanggal_masuk,
            status_karyawan=status_karyawan,
            status_aktif_karyawan=status_aktif_karyawan,
            password=get_password_hash(nik), 
            tempat_lahir=tempat_lahir,
            tanggal_lahir=tanggal_lahir,
            alamat=alamat,
            no_hp=no_hp,
            kontak_darurat_nama=kontak_darurat_nama,
            kontak_darurat_hp=kontak_darurat_hp,
            kontak_darurat_alamat=kontak_darurat_alamat,
            kode_status_kawin=kode_status_kawin,
            pendidikan_terakhir=pendidikan_terakhir,
            no_ijazah=no_ijazah,
            no_sim=no_sim,
            no_kartu_anggota=no_kartu_anggota,
            masa_aktif_kartu_anggota=masa_aktif_kartu_anggota,
            kode_jadwal=kode_jadwal,
            pin=pin,
            lock_location=lock_location,
            lock_device_login=lock_device_login,
            allow_multi_device=allow_multi_device,
            lock_jam_kerja=lock_jam_kerja,
            lock_patrol=lock_patrol,
            
            foto=foto_path,
            foto_ktp=foto_ktp_path,
            foto_kartu_anggota=foto_ka_path,
            foto_ijazah=foto_ijazah_path,
            foto_sim=foto_sim_path,
            
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(new_karyawan)
        db.commit()
        db.refresh(new_karyawan)
        
        return {"status": True, "message": "Karyawan berhasil ditambahkan", "data": {"nik": nik}}
        
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class KaryawanUserDTO(BaseModel):
    username: str
    email: str

class KaryawanWajahDTO(BaseModel):
    id: int
    wajah: Optional[str]

class KaryawanDetailDTO(KaryawanDTO):
    user: Optional[KaryawanUserDTO] = None
    wajah: Optional[List[KaryawanWajahDTO]] = []

class KaryawanDetailResponse(BaseModel):
    status: bool
    data: Optional[KaryawanDetailDTO] = None
    message: Optional[str] = None

@router.get("/karyawan/{nik}", response_model=KaryawanDetailResponse)
async def get_karyawan_detail(
    nik: str,
    current_user: CurrentUser = Depends(require_permission_dependency("karyawan.index")),
    db: Session = Depends(get_db)
):
    # Prevent processing 'undefined' from frontend mistakes
    if nik == "undefined":
        print("Warning: Received 'undefined' NIK in get_karyawan_detail")
        raise HTTPException(status_code=404, detail="Invalid NIK")

    try:
        sisa_hari_col = func.datediff(Karyawan.masa_aktif_kartu_anggota, func.current_date())
        
        row = db.query(
            Karyawan,
            Departemen.nama_dept,
            Jabatan.nama_jabatan,
            Cabang.nama_cabang,
            StatusKawin.status_kawin.label("keterangan_status_kawin"),
            Userkaryawan.id_user,
            sisa_hari_col.label("sisa_hari_anggota")
        ).outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
         .outerjoin(Jabatan, Karyawan.kode_jabatan == Jabatan.kode_jabatan)\
         .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
         .outerjoin(StatusKawin, Karyawan.kode_status_kawin == StatusKawin.kode_status_kawin)\
         .outerjoin(Userkaryawan, Karyawan.nik == Userkaryawan.nik)\
         .filter(Karyawan.nik == nik)\
         .first()

        if not row:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
            
        k = row[0] # Karyawan instance
        nama_dept = row[1]
        nama_jabatan = row[2]
        nama_cabang = row[3]
        keterangan_status_kawin = row[4]
        id_user = row[5]
        sisa_hari_anggota = row[6]
        
        # 2. Get User Info
        user_info = None
        if id_user:
            user_obj = db.query(Users).filter(Users.id == id_user).first()
            if user_obj:
                user_info = KaryawanUserDTO(username=user_obj.username, email=user_obj.email)
                
        # 3. Get Wajah Info
        wajah_list = []
        wajah_rows = db.query(KaryawanWajah).filter(KaryawanWajah.nik == nik).all()
        
        # Determine folder name based on legacy logic: {nik}-{firstname_lower}
        # Example: 123-budi
        first_name = k.nama_karyawan.split(' ')[0].lower() if k.nama_karyawan else "unknown"
        wajah_folder = f"storage/uploads/facerecognition/{nik}-{first_name}"

        for w in wajah_rows:
            wajah_list.append(KaryawanWajahDTO(
                id=w.id,
                wajah=get_full_image_url(w.wajah, folder=wajah_folder)
            ))

        data_dto = KaryawanDetailDTO(
            nik=k.nik,
            nama_karyawan=k.nama_karyawan,
            no_hp=k.no_hp,
            foto=get_full_image_url(k.foto),
            status_aktif_karyawan=k.status_aktif_karyawan,
            
            nama_dept=nama_dept or "-",
            nama_jabatan=nama_jabatan or "-",
            nama_cabang=nama_cabang or "-",

            kode_cabang=k.kode_cabang,
            kode_dept=k.kode_dept,
            kode_jabatan=k.kode_jabatan,
            kode_status_kawin=k.kode_status_kawin,
            jenis_kelamin=k.jenis_kelamin,
            status_karyawan=k.status_karyawan,
            tempat_lahir=k.tempat_lahir,
            tanggal_lahir=k.tanggal_lahir,
            alamat=k.alamat,
            
            no_ktp=k.no_ktp,
            tanggal_masuk=k.tanggal_masuk,
            no_kartu_anggota=k.no_kartu_anggota,
            masa_aktif_kartu_anggota=k.masa_aktif_kartu_anggota,
            keterangan_status_kawin=keterangan_status_kawin,
            pendidikan_terakhir=k.pendidikan_terakhir,
            no_ijazah=k.no_ijazah,
            kontak_darurat_nama=k.kontak_darurat_nama,
            kontak_darurat_hp=k.kontak_darurat_hp,
            kontak_darurat_alamat=k.kontak_darurat_alamat,
            lock_location=k.lock_location,
            lock_jam_kerja=k.lock_jam_kerja,
            lock_device_login=k.lock_device_login,
            allow_multi_device=k.allow_multi_device,
            pin=k.pin,
            foto_ktp=get_full_image_url(k.foto_ktp, folder="storage/karyawan/ktp"),
            foto_kartu_anggota=get_full_image_url(k.foto_kartu_anggota, folder="storage/karyawan/kartu"),
            foto_ijazah=get_full_image_url(k.foto_ijazah, folder="storage/karyawan/ijazah"),
            no_sim=k.no_sim,
            kode_jadwal=k.kode_jadwal,
            id_user=id_user,
            sisa_hari_anggota=sisa_hari_anggota,
            
            user=user_info,
            wajah=wajah_list
        )
        
        return KaryawanDetailResponse(status=True, data=data_dto)

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/karyawan/{nik}")
async def update_karyawan(
    nik: str,
    nama_karyawan: str = Form(...),
    no_ktp: str = Form(...),
    jenis_kelamin: str = Form(...),
    kode_cabang: str = Form(...),
    kode_dept: str = Form(...),
    kode_jabatan: str = Form(...),
    status_karyawan: str = Form(...),
    status_aktif_karyawan: str = Form(...),
    
    # Optional but usually present in update forms
    password: Optional[str] = Form(None), 
    tanggal_masuk: Optional[date] = Form(None),
    
    tempat_lahir: Optional[str] = Form(None),
    tanggal_lahir: Optional[date] = Form(None),
    alamat: Optional[str] = Form(None),
    no_hp: Optional[str] = Form(None),
    kontak_darurat_nama: Optional[str] = Form(None),
    kontak_darurat_hp: Optional[str] = Form(None),
    kontak_darurat_alamat: Optional[str] = Form(None),
    kode_status_kawin: Optional[str] = Form(None),
    pendidikan_terakhir: Optional[str] = Form(None),
    no_ijazah: Optional[str] = Form(None),
    no_sim: Optional[str] = Form(None),
    no_kartu_anggota: Optional[str] = Form(None),
    masa_aktif_kartu_anggota: Optional[date] = Form(None),
    kode_jadwal: Optional[str] = Form(None),
    pin: Optional[int] = Form(None),
    
    lock_location: str = Form('1'),
    lock_device_login: str = Form('0'),
    allow_multi_device: str = Form('0'),
    lock_jam_kerja: str = Form('1'),
    lock_patrol: str = Form('1'),
    
    foto: UploadFile = File(None),
    foto_ktp: UploadFile = File(None),
    foto_kartu_anggota: UploadFile = File(None),
    foto_ijazah: UploadFile = File(None),
    foto_sim: UploadFile = File(None),
    
    current_user: CurrentUser = Depends(require_permission_dependency("karyawan.update")),
    db: Session = Depends(get_db)
):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
            
        karyawan.nama_karyawan = nama_karyawan
        karyawan.no_ktp = no_ktp
        karyawan.jenis_kelamin = jenis_kelamin
        karyawan.kode_cabang = kode_cabang
        karyawan.kode_dept = kode_dept
        karyawan.kode_jabatan = kode_jabatan
        karyawan.status_karyawan = status_karyawan
        karyawan.status_aktif_karyawan = status_aktif_karyawan
        
        if password and len(password.strip()) > 0:
            karyawan.password = get_password_hash(password)
            
        if tanggal_masuk: 
            karyawan.tanggal_masuk = tanggal_masuk
            
        karyawan.tempat_lahir = tempat_lahir
        karyawan.tanggal_lahir = tanggal_lahir
        karyawan.alamat = alamat
        karyawan.no_hp = no_hp
        karyawan.kontak_darurat_nama = kontak_darurat_nama
        karyawan.kontak_darurat_hp = kontak_darurat_hp
        karyawan.kontak_darurat_alamat = kontak_darurat_alamat
        karyawan.kode_status_kawin = kode_status_kawin
        karyawan.pendidikan_terakhir = pendidikan_terakhir
        karyawan.no_ijazah = no_ijazah
        karyawan.no_sim = no_sim
        karyawan.no_kartu_anggota = no_kartu_anggota
        karyawan.masa_aktif_kartu_anggota = masa_aktif_kartu_anggota
        karyawan.kode_jadwal = kode_jadwal
        karyawan.pin = pin
        
        karyawan.lock_location = lock_location
        karyawan.lock_device_login = lock_device_login
        karyawan.allow_multi_device = allow_multi_device
        karyawan.lock_jam_kerja = lock_jam_kerja
        karyawan.lock_patrol = lock_patrol
        
        # Handle files only if uploaded
        if foto: 
            path = save_upload(foto, "")
            if path: karyawan.foto = path
            
        if foto_ktp:
            path = save_upload(foto_ktp, "ktp") 
            if path: karyawan.foto_ktp = path
            
        if foto_kartu_anggota:
            path = save_upload(foto_kartu_anggota, "kartu")
            if path: karyawan.foto_kartu_anggota = path
            
        if foto_ijazah:
            path = save_upload(foto_ijazah, "ijazah")
            if path: karyawan.foto_ijazah = path
            
        if foto_sim:
            path = save_upload(foto_sim, "sim")
            if path: karyawan.foto_sim = path
            
        karyawan.updated_at = datetime.now()
        
        db.commit()
        db.refresh(karyawan)
        
        return {"status": True, "message": "Karyawan berhasil diperbarui"}
        
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/karyawan/{nik}")
async def delete_karyawan(
    nik: str,
    current_user: CurrentUser = Depends(require_permission_dependency("karyawan.delete")),
    db: Session = Depends(get_db)
):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
            
        db.delete(karyawan)
        db.commit()
        return {"status": True, "message": "Karyawan berhasil dihapus"}
    except Exception as e:
        db.rollback()
        if "foreign key constraint" in str(e).lower():
             raise HTTPException(status_code=400, detail="Tidak dapat menghapus karyawan karena ada data terkait")
        raise HTTPException(status_code=500, detail=str(e))

# --------------------------------------------------------------------------------------
# NEW TOGGLE ENDPOINTS
# --------------------------------------------------------------------------------------

@router.patch("/karyawan/{nik}/toggle/location")
async def toggle_location(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Toggle lock_location ('1' -> '0', '0' -> '1')
        new_val = '0' if karyawan.lock_location == '1' else '1'
        karyawan.lock_location = new_val
        db.commit()
        db.refresh(karyawan)
        
        return {"status": True, "message": f"Lock Location updated to {new_val}", "data": new_val}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/karyawan/{nik}/toggle/jamkerja")
async def toggle_jamkerja(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Toggle lock_jam_kerja
        new_val = '0' if karyawan.lock_jam_kerja == '1' else '1'
        karyawan.lock_jam_kerja = new_val
        db.commit()
        
        return {"status": True, "message": f"Lock Jam Kerja updated to {new_val}", "data": new_val}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/karyawan/{nik}/toggle/device")
async def toggle_device(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Toggle lock_device_login
        new_val = '0' if karyawan.lock_device_login == '1' else '1'
        karyawan.lock_device_login = new_val
        db.commit()
        
        return {"status": True, "message": f"Lock Device updated to {new_val}", "data": new_val}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/karyawan/{nik}/toggle/multidevice")
async def toggle_multidevice(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Toggle allow_multi_device
        new_val = '0' if karyawan.allow_multi_device == '1' else '1'
        karyawan.allow_multi_device = new_val
        db.commit()
        
        return {"status": True, "message": f"Allow Multi Device updated to {new_val}", "data": new_val}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/karyawan/{nik}/reset-session")
async def reset_session(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # 1. Reset Lock
        karyawan.lock_device_login = '0'
        
        # 2. Invalidate Session (Force Logout)
        # Find User ID associated with Karyawan
        user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.nik == nik).first()
        
        msg_extra = ""
        if user_karyawan:
            user = db.query(Users).filter(Users.id == user_karyawan.id_user).first()
            if user:
                # Update updated_at to invalidate tokens issued before now
                user.updated_at = datetime.utcnow()
                db.add(user)
                msg_extra = " & Token Invalidated"
        
        db.commit()
        
        return {"status": True, "message": f"Sesi berhasil direset (Lock Device dibuka){msg_extra}."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------------------
# JAM KERJA ENDPOINTS
# --------------------------------------------------------------------------------------

# DTO defined inside function to avoid forward ref issues if any, or place near top.
# For simplicity and speed, using dict/Body or defining here.

class JamKerjaItemDTO(BaseModel):
    hari: str
    kode_jam_kerja: Optional[str]

class SetJamKerjaDTO(BaseModel):
    jam_by_day: List[JamKerjaItemDTO] 

@router.get("/jam-kerja-options")
async def get_jam_kerja_options(db: Session = Depends(get_db)):
    try:
        data = db.query(PresensiJamkerja).order_by(PresensiJamkerja.nama_jam_kerja).all()
        return [{"kode_jam_kerja": r.kode_jam_kerja, "nama_jam_kerja": r.nama_jam_kerja, "jam_masuk": str(r.jam_masuk), "jam_pulang": str(r.jam_pulang)} for r in data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/karyawan/{nik}/jam-kerja")
async def get_karyawan_jam_kerja(nik: str, db: Session = Depends(get_db)):
    try:
        by_day = db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik).all()
        return {
            "by_day": [{"hari": r.hari, "kode_jam_kerja": r.kode_jam_kerja} for r in by_day]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/karyawan/{nik}/jam-kerja")
async def save_karyawan_jam_kerja(nik: str, payload: SetJamKerjaDTO, db: Session = Depends(get_db)):
    try:
        # Delete existing by day for this NIK
        db.query(SetJamKerjaByDay).filter(SetJamKerjaByDay.nik == nik).delete(synchronize_session=False)
        
        # Insert new
        records = []
        for item in payload.jam_by_day:
            if item.kode_jam_kerja:
                 records.append(SetJamKerjaByDay(
                     nik=nik,
                     hari=item.hari,
                     kode_jam_kerja=item.kode_jam_kerja
                 ))
        
        if records:
            db.add_all(records)
            
        db.commit()
        return {"status": True, "message": "Jam kerja berhasil disimpan"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------------------
# JAM KERJA BY DATE (Jadwal Harian & Extra)
# --------------------------------------------------------------------------------------

class JamKerjaDateDTO(BaseModel):
    tanggal: date
    kode_jam_kerja: str

class JamKerjaDateExtraDTO(BaseModel):
    tanggal: date
    kode_jam_kerja: str
    jenis: str = "double_shift"
    keterangan: Optional[str] = None

@router.get("/karyawan/{nik}/jam-kerja-date")
async def get_jam_kerja_by_date(nik: str, bulan: int = Query(...), tahun: int = Query(...), db: Session = Depends(get_db)):
    try:
        data = db.query(SetJamKerjaByDate, PresensiJamkerja)\
            .join(PresensiJamkerja, SetJamKerjaByDate.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .filter(SetJamKerjaByDate.nik == nik)\
            .filter(func.month(SetJamKerjaByDate.tanggal) == bulan)\
            .filter(func.year(SetJamKerjaByDate.tanggal) == tahun)\
            .order_by(SetJamKerjaByDate.tanggal).all()
            
        return [
            {
                "nik": r[0].nik,
                "tanggal": r[0].tanggal,
                "kode_jam_kerja": r[0].kode_jam_kerja,
                "nama_jam_kerja": r[1].nama_jam_kerja,
                "jam_masuk": str(r[1].jam_masuk),
                "jam_pulang": str(r[1].jam_pulang)
            }
            for r in data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/karyawan/{nik}/jam-kerja-date")
async def create_jam_kerja_by_date(nik: str, payload: JamKerjaDateDTO, db: Session = Depends(get_db)):
    try:
        # Cek duplicate
        existing = db.query(SetJamKerjaByDate).filter(
            SetJamKerjaByDate.nik == nik, 
            SetJamKerjaByDate.tanggal == payload.tanggal
        ).first()
        
        if existing:
            # Update existing
            existing.kode_jam_kerja = payload.kode_jam_kerja
        else:
            # Create new
            new_item = SetJamKerjaByDate(
                nik=nik,
                tanggal=payload.tanggal,
                kode_jam_kerja=payload.kode_jam_kerja,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_item)
            
        db.commit()
        return {"status": True, "message": "Jadwal berhasil disimpan"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/karyawan/{nik}/jam-kerja-date")
async def delete_jam_kerja_by_date(nik: str, tanggal: date = Query(...), db: Session = Depends(get_db)):
    try:
        db.query(SetJamKerjaByDate).filter(
            SetJamKerjaByDate.nik == nik,
            SetJamKerjaByDate.tanggal == tanggal
        ).delete()
        db.commit()
        return {"status": True, "message": "Jadwal berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# EXTRA JAM KERJA

@router.get("/karyawan/{nik}/jam-kerja-extra")
async def get_jam_kerja_extra(nik: str, bulan: int = Query(...), tahun: int = Query(...), db: Session = Depends(get_db)):
    try:
        data = db.query(PresensiJamkerjaBydateExtra, PresensiJamkerja)\
            .join(PresensiJamkerja, PresensiJamkerjaBydateExtra.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)\
            .filter(PresensiJamkerjaBydateExtra.nik == nik)\
            .filter(func.month(PresensiJamkerjaBydateExtra.tanggal) == bulan)\
            .filter(func.year(PresensiJamkerjaBydateExtra.tanggal) == tahun)\
            .order_by(PresensiJamkerjaBydateExtra.tanggal).all()
            
        return [
            {
                "nik": r[0].nik,
                "tanggal": r[0].tanggal,
                "kode_jam_kerja": r[0].kode_jam_kerja,
                "jenis": r[0].jenis,
                "keterangan": r[0].keterangan,
                "nama_jam_kerja": r[1].nama_jam_kerja,
                "jam_masuk": str(r[1].jam_masuk),
                "jam_pulang": str(r[1].jam_pulang)
            }
            for r in data
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/karyawan/{nik}/jam-kerja-extra")
async def create_jam_kerja_extra(nik: str, payload: JamKerjaDateExtraDTO, db: Session = Depends(get_db)):
    try:
        # Max 1 per tanggal validation? Laravel says "Max 1 per tanggal"
        existing = db.query(PresensiJamkerjaBydateExtra).filter(
            PresensiJamkerjaBydateExtra.nik == nik,
            PresensiJamkerjaBydateExtra.tanggal == payload.tanggal
        ).first()
        
        if existing:
            # Update existing
            existing.kode_jam_kerja = payload.kode_jam_kerja
            existing.jenis = payload.jenis
            existing.keterangan = payload.keterangan
            existing.updated_at = datetime.now()
        else:
            new_item = PresensiJamkerjaBydateExtra(
                nik=nik,
                tanggal=payload.tanggal,
                kode_jam_kerja=payload.kode_jam_kerja,
                jenis=payload.jenis,
                keterangan=payload.keterangan or "",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            db.add(new_item)
            
        db.commit()
        return {"status": True, "message": "Jadwal Tambahan berhasil disimpan"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/karyawan/{nik}/jam-kerja-extra")
async def delete_jam_kerja_extra(nik: str, tanggal: date = Query(...), db: Session = Depends(get_db)):
    try:
        db.query(PresensiJamkerjaBydateExtra).filter(
            PresensiJamkerjaBydateExtra.nik == nik,
            PresensiJamkerjaBydateExtra.tanggal == tanggal
        ).delete()
        db.commit()
        return {"status": True, "message": "Jadwal Tambahan berhasil dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --------------------------------------------------------------------------------------
# USER MANAGEMENT (Create / Delete Akun Login)
# --------------------------------------------------------------------------------------

@router.post("/karyawan/{nik}/create-user")
async def create_user_from_karyawan(nik: str, db: Session = Depends(get_db)):
    try:
        karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
        if not karyawan:
            raise HTTPException(status_code=404, detail="Karyawan tidak ditemukan")
        
        # Check existing Userkaryawan
        existing_link = db.query(Userkaryawan).filter(Userkaryawan.nik == nik).first()
        if existing_link:
             raise HTTPException(status_code=400, detail="Karyawan sudah memiliki akun user")

        # Create User
        # Default password = NIK (Hash)
        hashed_password = get_password_hash(nik)
        
        # Email format: nik without dots + @k3guard.com
        email_prefix = nik.replace(".", "").lower()
        email = f"{email_prefix}@k3guard.com"
        
        # Check username/email collision
        if db.query(Users).filter((Users.username == nik) | (Users.email == email)).first():
             raise HTTPException(status_code=400, detail="Username/Email sudah digunakan")
        
        new_user = Users(
            name=karyawan.nama_karyawan,
            username=nik,
            email=email, 
            password=hashed_password,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_user)
        db.flush() 
        
        # Link to Karyawan (Userkaryawan)
        new_link = Userkaryawan(
            nik=nik,
            id_user=new_user.id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_link)
        
        db.commit()
        return {"status": True, "message": f"User berhasil dibuat. Password default: {nik}"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/karyawan/{nik}/delete-user")
async def delete_user_from_karyawan(nik: str, db: Session = Depends(get_db)):
    try:
        # Check link
        user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.nik == nik).first()
        if not user_karyawan:
            raise HTTPException(status_code=400, detail="Karyawan belum memiliki akun user")
            
        user_id = user_karyawan.id_user
        
        # Delete Link
        db.delete(user_karyawan)
        
        # Delete User
        user = db.query(Users).filter(Users.id == user_id).first()
        if user:
            db.delete(user)
            
        db.commit()
        return {"status": True, "message": "User berhasil dihapus"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
