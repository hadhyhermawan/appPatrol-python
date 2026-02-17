from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database import get_db
from app.models.models import Presensi, Karyawan, Departemen, PresensiJamkerja
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime

router = APIRouter(
    prefix="/api/monitoring",
    tags=["Monitoring"]
)

class PresensiItem(BaseModel):
    id: int
    nik: str
    nama_karyawan: Optional[str]
    nama_dept: Optional[str]
    nama_jam_kerja: Optional[str]
    jam_in: Optional[str] 
    jam_out: Optional[str]
    foto_in: Optional[str]
    foto_out: Optional[str]
    lokasi_in: Optional[str]
    lokasi_out: Optional[str]
    status_kehadiran: Optional[str]

class PaginationMeta(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    per_page: int

class MonitoringResponse(BaseModel):
    status: bool
    message: str
    data: List[PresensiItem]
    meta: Optional[PaginationMeta] = None

@router.get("/presensi", response_model=MonitoringResponse)
async def get_monitoring_presensi(
    date: Optional[date] = Query(None, description="Tanggal monitoring YYYY-MM-DD. Jika kosong tampilkan semua."),
    dept_code: Optional[str] = Query(None, description="Kode Departemen Filter"),
    page: int = Query(1, ge=1, description="Nomor Halaman"),
    per_page: int = Query(20, ge=1, le=100, description="Jumlah per halaman"),
    db: Session = Depends(get_db)
):
    try:
        # Build Query
        query = db.query(
            Presensi.id,
            Presensi.nik,
            Karyawan.nama_karyawan,
            Departemen.nama_dept,
            PresensiJamkerja.nama_jam_kerja,
            Presensi.jam_in,
            Presensi.jam_out,
            Presensi.foto_in,
            Presensi.foto_out,
            Presensi.lokasi_in,
            Presensi.lokasi_out,
            Presensi.status
        ).outerjoin(Karyawan, Presensi.nik == Karyawan.nik)\
         .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)\
         .outerjoin(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)
        
        # Filter by Date (Optional)
        if date:
            query = query.filter(Presensi.tanggal == date)
        
        # Filter by Dept
        if dept_code:
            query = query.filter(Karyawan.kode_dept == dept_code)
            
        # Total Count (Before Pagination)
        total_items = query.count()
        
        # Order and Pagination
        query = query.order_by(Presensi.jam_in.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)
        
        results = query.all()
        
        # Calculate pagination meta
        import math
        total_pages = math.ceil(total_items / per_page)
        
        data_list = []
        for row in results:
            # Format time
            jin = row.jam_in.strftime("%H:%M:%S") if row.jam_in else "-"
            jout = row.jam_out.strftime("%H:%M:%S") if row.jam_out else "-"
            
            item = PresensiItem(
                id=row.id,
                nik=row.nik,
                nama_karyawan=row.nama_karyawan or "Unknown",
                nama_dept=row.nama_dept or "-",
                nama_jam_kerja=row.nama_jam_kerja or "-",
                jam_in=jin,
                jam_out=jout,
                foto_in=row.foto_in,
                foto_out=row.foto_out,
                lokasi_in=row.lokasi_in,
                lokasi_out=row.lokasi_out,
                status_kehadiran=row.status
            )
            data_list.append(item)
            
        return MonitoringResponse(
            status=True, 
            message="Data presensi berhasil diambil",
            data=data_list,
            meta=PaginationMeta(
                total_items=total_items,
                total_pages=total_pages,
                current_page=page,
                per_page=per_page
            )
        )

    except Exception as e:
        print(f"ERROR MONITORING: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/presensi/{id}")
async def delete_monitoring_presensi(id: int, db: Session = Depends(get_db)):
    try:
        presensi = db.query(Presensi).filter(Presensi.id == id).first()
        if not presensi:
            raise HTTPException(status_code=404, detail="Data presensi tidak ditemukan")
            
        db.delete(presensi)
        db.commit()
        
        return {"status": True, "message": "Data presensi berhasil dihapus"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR DELETE PRESENSI: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
