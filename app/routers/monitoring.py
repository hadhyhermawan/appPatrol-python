from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.database import get_db
from app.models.models import Presensi, Karyawan, Departemen, PresensiJamkerja, Cabang
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime, time
from app.routers.master import get_full_image_url
from app.core.permissions import get_current_user
import math

router = APIRouter(
    prefix="/api/monitoring",
    tags=["Monitoring"],
    dependencies=[Depends(get_current_user)]
)

# ─── Schemas ──────────────────────────────────────────────────────────────────

class PresensiItem(BaseModel):
    id: int
    nik: str
    nama_karyawan: Optional[str]
    nama_dept: Optional[str]
    nama_cabang: Optional[str]
    nama_jam_kerja: Optional[str]
    jam_in: Optional[str]
    jam_out: Optional[str]
    foto_in: Optional[str]
    foto_out: Optional[str]
    lokasi_in: Optional[str]
    lokasi_out: Optional[str]
    status_kehadiran: Optional[str]
    kode_jam_kerja: Optional[str] = None
    tanggal: Optional[str] = None

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

class PresensiUpdatePayload(BaseModel):
    jam_in: Optional[str] = None        # "HH:MM" atau "HH:MM:SS"
    jam_out: Optional[str] = None       # "HH:MM" atau "HH:MM:SS", kosong = hapus jam_out
    status: Optional[str] = None        # H / I / S / A
    kode_jam_kerja: Optional[str] = None


# ─── Helper ───────────────────────────────────────────────────────────────────

def _parse_to_datetime(val: Optional[str], ref_date: date) -> Optional[datetime]:
    """Parse 'HH:MM' atau 'HH:MM:SS' menjadi datetime (dengan tanggal dari record presensi)."""
    if not val or val.strip() in ('-', ''):
        return None
    parts = val.strip().split(':')
    try:
        h, m = int(parts[0]), int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
        return datetime.combine(ref_date, time(h, m, s))
    except Exception:
        return None


# ─── GET: Daftar Presensi (paginasi + filter) ─────────────────────────────────

@router.get("/presensi", response_model=MonitoringResponse)
async def get_monitoring_presensi(
    date: Optional[date] = Query(None),
    dept_code: Optional[str] = Query(None),
    cabang_code: Optional[str] = Query(None),
    kode_jam_kerja: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(
            Presensi.id,
            Presensi.nik,
            Karyawan.nama_karyawan,
            Departemen.nama_dept,
            Cabang.nama_cabang,
            PresensiJamkerja.nama_jam_kerja,
            Presensi.jam_in,
            Presensi.jam_out,
            Presensi.foto_in,
            Presensi.foto_out,
            Presensi.lokasi_in,
            Presensi.lokasi_out,
            Presensi.status,
            Presensi.kode_jam_kerja,
            Presensi.tanggal,
        ).outerjoin(Karyawan, Presensi.nik == Karyawan.nik) \
         .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept) \
         .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang) \
         .outerjoin(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja)

        if date:
            query = query.filter(Presensi.tanggal == date)
        if dept_code:
            query = query.filter(Karyawan.kode_dept == dept_code)
        if cabang_code:
            query = query.filter(Karyawan.kode_cabang == cabang_code)
        if kode_jam_kerja:
            query = query.filter(Presensi.kode_jam_kerja == kode_jam_kerja)
        if search:
            st = f"%{search}%"
            query = query.filter(
                (Karyawan.nama_karyawan.ilike(st)) | (Presensi.nik.ilike(st))
            )

        total_items = query.count()
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1

        results = query.order_by(Presensi.jam_in.desc()) \
                       .offset((page - 1) * per_page).limit(per_page).all()

        data_list = [
            PresensiItem(
                id=row.id,
                nik=row.nik,
                nama_karyawan=row.nama_karyawan or "Unknown",
                nama_dept=row.nama_dept or "-",
                nama_cabang=row.nama_cabang or "-",
                nama_jam_kerja=row.nama_jam_kerja or "-",
                jam_in=row.jam_in.strftime("%H:%M:%S") if row.jam_in else "-",
                jam_out=row.jam_out.strftime("%H:%M:%S") if row.jam_out else "-",
                foto_in=get_full_image_url(row.foto_in, "storage/uploads/absensi") if row.foto_in else None,
                foto_out=get_full_image_url(row.foto_out, "storage/uploads/absensi") if row.foto_out else None,
                lokasi_in=row.lokasi_in,
                lokasi_out=row.lokasi_out,
                status_kehadiran=row.status,
                kode_jam_kerja=row.kode_jam_kerja,
                tanggal=str(row.tanggal) if row.tanggal else None,
            )
            for row in results
        ]

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
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET: Detail Presensi ─────────────────────────────────────────────────────

@router.get("/presensi/{id}", response_model=PresensiItem)
async def get_monitoring_presensi_detail(id: int, db: Session = Depends(get_db)):
    try:
        result = db.query(
            Presensi, Karyawan.nama_karyawan, Departemen.nama_dept, Cabang.nama_cabang, PresensiJamkerja.nama_jam_kerja
        ).outerjoin(Karyawan, Presensi.nik == Karyawan.nik) \
         .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept) \
         .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang) \
         .outerjoin(PresensiJamkerja, Presensi.kode_jam_kerja == PresensiJamkerja.kode_jam_kerja) \
         .filter(Presensi.id == id).first()

        if not result:
            raise HTTPException(status_code=404, detail="Data presensi tidak ditemukan")

        presensi, nama_karyawan, nama_dept, nama_cabang, nama_jam_kerja = result
        return PresensiItem(
            id=presensi.id,
            nik=presensi.nik,
            nama_karyawan=nama_karyawan or "Unknown",
            nama_dept=nama_dept or "-",
            nama_cabang=nama_cabang or "-",
            nama_jam_kerja=nama_jam_kerja or "-",
            jam_in=presensi.jam_in.strftime("%H:%M:%S") if presensi.jam_in else "-",
            jam_out=presensi.jam_out.strftime("%H:%M:%S") if presensi.jam_out else "-",
            foto_in=get_full_image_url(presensi.foto_in, "storage/uploads/absensi") if presensi.foto_in else None,
            foto_out=get_full_image_url(presensi.foto_out, "storage/uploads/absensi") if presensi.foto_out else None,
            lokasi_in=presensi.lokasi_in,
            lokasi_out=presensi.lokasi_out,
            status_kehadiran=presensi.status,
            kode_jam_kerja=presensi.kode_jam_kerja,
            tanggal=str(presensi.tanggal) if presensi.tanggal else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── PUT: Edit Presensi ───────────────────────────────────────────────────────

@router.put("/presensi/{id}")
async def update_monitoring_presensi(
    id: int,
    payload: PresensiUpdatePayload,
    db: Session = Depends(get_db)
):
    """Edit jam_in, jam_out, status, dan shift karyawan."""
    try:
        presensi = db.query(Presensi).filter(Presensi.id == id).first()
        if not presensi:
            raise HTTPException(status_code=404, detail="Data presensi tidak ditemukan")

        # Ambil tanggal dari record untuk membentuk datetime lengkap
        ref_date = presensi.tanggal if presensi.tanggal else date.today()

        if payload.jam_in is not None:
            presensi.jam_in = _parse_to_datetime(payload.jam_in, ref_date)
        if payload.jam_out is not None:
            presensi.jam_out = _parse_to_datetime(payload.jam_out, ref_date)
        if payload.status is not None:
            presensi.status = payload.status.upper()
        if payload.kode_jam_kerja is not None:
            presensi.kode_jam_kerja = payload.kode_jam_kerja or None

        db.commit()

        # Format response — ambil hanya bagian jam dari datetime/time/string
        def fmt_time(t) -> str:
            if t is None:
                return "-"
            if isinstance(t, datetime):
                return t.strftime("%H:%M:%S")
            if isinstance(t, time):
                return t.strftime("%H:%M:%S")
            # Fallback string
            s = str(t)
            if ' ' in s:           # datetime string: "2025-01-01 08:00:00"
                s = s.split(' ')[1]
            return s[:8] if s else "-"

        return {
            "status": True,
            "message": "Data presensi berhasil diupdate",
            "data": {
                "id": presensi.id,
                "jam_in": fmt_time(presensi.jam_in),
                "jam_out": fmt_time(presensi.jam_out),
                "status": presensi.status,
                "kode_jam_kerja": presensi.kode_jam_kerja,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR UPDATE PRESENSI: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ─── DELETE: Hapus Presensi ───────────────────────────────────────────────────

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
        raise HTTPException(status_code=500, detail=str(e))


# ─── GET: Opsi Jam Kerja (untuk dropdown modal edit) ─────────────────────────

@router.get("/jam-kerja-options")
async def get_jam_kerja_options(db: Session = Depends(get_db)):
    rows = db.query(PresensiJamkerja).order_by(PresensiJamkerja.nama_jam_kerja).all()
    return {
        "status": True,
        "data": [
            {
                "kode": r.kode_jam_kerja,
                "nama": r.nama_jam_kerja,
                "jam_masuk": str(r.jam_masuk) if r.jam_masuk else None,
                "jam_pulang": str(r.jam_pulang) if r.jam_pulang else None,
            }
            for r in rows
        ]
    }
