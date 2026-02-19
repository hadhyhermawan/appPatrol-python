from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database import get_db
from app.models.models import PatrolSessions, PatrolPoints, PatrolPointMaster, Karyawan, Cabang
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
from app.core.permissions import get_current_user
import os

router = APIRouter(
    prefix="/api/monitoring/patrol",
    tags=["Monitoring Patrol"],
    dependencies=[Depends(get_current_user)]
)

class PointDetail(BaseModel):
    id: int
    nama_titik: str
    jam: Optional[str]
    lokasi: Optional[str]
    foto: Optional[str]
    urutan: int
    latitude: Optional[float]
    longitude: Optional[float]

class PatrolDetailResponse(BaseModel):
    id: int
    tanggal: str
    jam_patrol: str
    nik: str
    nama_karyawan: str
    kode_cabang: str
    nama_cabang: Optional[str]
    status: str
    foto_absen: Optional[str]
    points: List[PointDetail]

@router.get("/{id}", response_model=PatrolDetailResponse)
async def get_patrol_detail(
    id: int = Path(..., description="ID Patrol Session"),
    db: Session = Depends(get_db)
):
    # 1. Get Session
    session = db.query(
        PatrolSessions,
        Karyawan.nama_karyawan,
        Karyawan.kode_cabang,
        Cabang.nama_cabang
    ).join(Karyawan, PatrolSessions.nik == Karyawan.nik)\
     .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
     .filter(PatrolSessions.id == id)\
     .first()
     
    if not session:
        raise HTTPException(status_code=404, detail="Data patrol tidak ditemukan")
        
    p_session = session[0] # PatrolSessions object
    nama_karyawan = session[1]
    kode_cabang = session[2]
    nama_cabang = session[3]
    
    # 2. Construct Foto Absen URL
    foto_absen_url = None
    if p_session.foto_absen:
        nik = p_session.nik
        ymd = p_session.tanggal.strftime('%Y%m%d')
        # Logic: uploads/patroli/{nik}-{ymd}-absenpatrol/{filename}
        # Assuming static file serving is configured for 'storage/uploads/patroli'
        # Adjust domain as needed. For now using relative path or full URL if configured.
        # Based on patroli_legacy.py:
        # https://frontend.k3guard.com/api-py/storage/uploads/patroli/{subfolder}/{filename}
        
        folder = f"{nik}-{ymd}-absenpatrol"
        foto_absen_url = f"https://frontend.k3guard.com/api-py/storage/uploads/patroli/{folder}/{os.path.basename(p_session.foto_absen)}"

    # 3. Get Points
    points_query = db.query(PatrolPoints, PatrolPointMaster)\
        .outerjoin(PatrolPointMaster, PatrolPoints.patrol_point_master_id == PatrolPointMaster.id)\
        .filter(PatrolPoints.patrol_session_id == id)\
        .order_by(PatrolPointMaster.urutan.asc())\
        .all()
        
    points_data = []
    for row in points_query:
        pp = row[0] # PatrolPoints
        bpm = row[1] # PatrolPointMaster
        
        foto_point_url = None
        if pp.foto:
            nik = p_session.nik
            ymd = p_session.tanggal.strftime('%Y%m%d')
            folder = f"{nik}-{ymd}-patrol"
            foto_point_url = f"https://frontend.k3guard.com/api-py/storage/uploads/patroli/{folder}/{os.path.basename(pp.foto)}"
            
        points_data.append(PointDetail(
            id=pp.id,
            nama_titik=bpm.nama_titik if bpm else "Unknown Point",
            jam=pp.jam.strftime("%H:%M") if pp.jam else None,
            lokasi=pp.lokasi,
            foto=foto_point_url,
            urutan=bpm.urutan if bpm else 0,
            latitude=float(bpm.latitude) if bpm and bpm.latitude else None,
            longitude=float(bpm.longitude) if bpm and bpm.longitude else None
        ))
        
    return PatrolDetailResponse(
        id=p_session.id,
        tanggal=str(p_session.tanggal),
        jam_patrol=p_session.jam_patrol.strftime("%H:%M") if p_session.jam_patrol else "-",
        nik=p_session.nik,
        nama_karyawan=nama_karyawan,
        kode_cabang=kode_cabang,
        nama_cabang=nama_cabang,
        status=p_session.status,
        foto_absen=foto_absen_url,
        points=points_data
    )
