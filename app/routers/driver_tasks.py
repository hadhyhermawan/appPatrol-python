from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from pydantic import BaseModel
from typing import Optional, List, Any
import datetime
import os
import secrets
from pathlib import Path

from app.database import get_db
from app.models.models import DriverJobOrders, DriverP2h, Users, Karyawan, Userkaryawan, MasterKendaraan
from app.core.permissions import require_permission_dependency, CurrentUser, get_current_user

router = APIRouter(prefix="/api/driver/tasks", tags=["Driver Tasks"])
router_android = APIRouter(prefix="/api/android/driver/tasks", tags=["Android Driver Tasks"])

# ==============================================================================
# WEB CRUD
# ==============================================================================

@router.get("")
def get_tasks(
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 10,
    db: Session = Depends(get_db)
):
    query = db.query(DriverJobOrders).outerjoin(Users, DriverJobOrders.user_id == Users.id) \
                                     .outerjoin(Userkaryawan, Users.id == Userkaryawan.id_user) \
                                     .outerjoin(Karyawan, Userkaryawan.nik == Karyawan.nik) \
                                     .outerjoin(DriverP2h, DriverJobOrders.p2h_id == DriverP2h.id) \
                                     .outerjoin(MasterKendaraan, DriverP2h.kendaraan_id == MasterKendaraan.id)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Karyawan.nama_karyawan.ilike(search_filter),
                DriverJobOrders.nama_tamu.ilike(search_filter),
                DriverJobOrders.tujuan_perjalanan.ilike(search_filter)
            )
        )
    
    total_items = query.count()
    total_pages = (total_items + per_page - 1) // per_page
    
    tasks = query.with_entities(
        DriverJobOrders, 
        Karyawan.nama_karyawan,
        MasterKendaraan.nama_kendaraan,
        MasterKendaraan.plat_nomor
    ).order_by(DriverJobOrders.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    
    result = []
    for t, driver_name, kendaraan_name, plat_nomor in tasks:
        result.append({
            "id": t.id,
            "user_id": t.user_id,
            "driver_name": driver_name or "Unknown",
            "p2h_id": t.p2h_id,
            "kendaraan_name": kendaraan_name if kendaraan_name else "-",
            "plat_nomor": plat_nomor if plat_nomor else "-",
            "nama_tamu": t.nama_tamu,
            "tujuan_perjalanan": t.tujuan_perjalanan,
            "lokasi_jemput": t.lokasi_jemput,
            "lokasi_tujuan": t.lokasi_tujuan,
            "jadwal_jemput": str(t.jadwal_jemput) if t.jadwal_jemput else None,
            "waktu_mulai": str(t.waktu_mulai) if t.waktu_mulai else None,
            "waktu_sampai_tujuan": str(t.waktu_sampai_tujuan) if t.waktu_sampai_tujuan else None,
            "status": t.status,
            "odometer_akhir_tugas": t.odometer_akhir_tugas,
            "keterangan_selesai": t.keterangan_selesai
        })
    
    return {
        "status": True,
        "message": "Data Tasks",
        "data": result,
        "meta": {
            "current_page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages
        }
    }

@router.get("/options")
def get_task_options(db: Session = Depends(get_db)):
    results = db.query(Users, Karyawan).join(
        Userkaryawan, Users.id == Userkaryawan.id_user
    ).join(
        Karyawan, Userkaryawan.nik == Karyawan.nik
    ).filter(
        or_(
            Karyawan.kode_dept == 'UDV',
            Karyawan.kode_jabatan == 'DRV'
        )
    ).all()
    
    driver_opts = [{"id": u.id, "name": k.nama_karyawan} for u, k in results]
    
    # Active P2H (Optional selection for tasks)
    p2h_list = db.query(DriverP2h).join(MasterKendaraan).order_by(DriverP2h.id.desc()).limit(100).all()
    p2h_opts = [{"id": p.id, "name": f"P2H {p.tanggal} - {p.kendaraan.nama_kendaraan if p.kendaraan else ''} ({p.kendaraan.plat_nomor if p.kendaraan else ''})"} for p in p2h_list]

    return {
        "drivers": driver_opts,
        "p2h": p2h_opts
    }

@router.get("/{id}")
def get_task_detail(id: int, db: Session = Depends(get_db)):
    t = db.query(DriverJobOrders).filter(DriverJobOrders.id == id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
        
    return {
        "status": True,
        "message": "Detail Task",
        "data": {
            "id": t.id,
            "user_id": t.user_id,
            "p2h_id": t.p2h_id,
            "nama_tamu": t.nama_tamu,
            "tujuan_perjalanan": t.tujuan_perjalanan,
            "lokasi_jemput": t.lokasi_jemput,
            "lokasi_tujuan": t.lokasi_tujuan,
            "jadwal_jemput": str(t.jadwal_jemput.strftime("%Y-%m-%dT%H:%M")) if t.jadwal_jemput else "",
            "status": t.status,
            "keterangan_selesai": t.keterangan_selesai
        }
    }

@router.post("")
def create_task(
    user_id: int = Form(...),
    p2h_id: int = Form(None),
    nama_tamu: str = Form(None),
    tujuan_perjalanan: str = Form(None),
    lokasi_jemput: str = Form(None),
    lokasi_tujuan: str = Form(None),
    jadwal_jemput: str = Form(None),
    db: Session = Depends(get_db)
):
    jadwal_obj = None
    if jadwal_jemput:
        try:
            jadwal_obj = datetime.datetime.strptime(jadwal_jemput, "%Y-%m-%dT%H:%M")
        except:
            jadwal_obj = None

    new_task = DriverJobOrders(
        user_id=user_id,
        p2h_id=p2h_id,
        nama_tamu=nama_tamu,
        tujuan_perjalanan=tujuan_perjalanan,
        lokasi_jemput=lokasi_jemput,
        lokasi_tujuan=lokasi_tujuan,
        jadwal_jemput=jadwal_obj,
        status='ASSIGNED',
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now()
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return {"status": True, "message": "Job Order berhasil dibuat", "data": {"id": new_task.id}}

@router.put("/{id}")
def update_task(
    id: int,
    user_id: int = Form(...),
    p2h_id: int = Form(None),
    nama_tamu: str = Form(None),
    tujuan_perjalanan: str = Form(None),
    lokasi_jemput: str = Form(None),
    lokasi_tujuan: str = Form(None),
    jadwal_jemput: str = Form(None),
    status: str = Form("ASSIGNED"),
    db: Session = Depends(get_db)
):
    t = db.query(DriverJobOrders).filter(DriverJobOrders.id == id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")

    jadwal_obj = t.jadwal_jemput
    if jadwal_jemput:
        try:
            jadwal_obj = datetime.datetime.strptime(jadwal_jemput, "%Y-%m-%dT%H:%M")
        except:
            pass

    t.user_id = user_id
    t.p2h_id = p2h_id if p2h_id else None
    t.nama_tamu = nama_tamu
    t.tujuan_perjalanan = tujuan_perjalanan
    t.lokasi_jemput = lokasi_jemput
    t.lokasi_tujuan = lokasi_tujuan
    t.jadwal_jemput = jadwal_obj
    t.status = status
    t.updated_at = datetime.datetime.now()
    
    db.commit()
    return {"status": True, "message": "Job Order berhasil diupdate"}

@router.delete("/{id}")
def delete_task(id: int, db: Session = Depends(get_db)):
    t = db.query(DriverJobOrders).filter(DriverJobOrders.id == id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan")
        
    db.delete(t)
    db.commit()
    return {"status": True, "message": "Job Order berhasil dihapus"}

# ==============================================================================
# ANDROID ENDPOINTS
# ==============================================================================

@router_android.get("/my-tasks")
def get_android_my_tasks(
    status: Optional[str] = None, # ASSIGNED, COMPLETED, etc
    page: int = 1,
    per_page: int = 10,
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(DriverJobOrders).filter(DriverJobOrders.user_id == current_user.id)
    if status:
        query = query.filter(DriverJobOrders.status == status)
        
    total_items = query.count()
    total_pages = (total_items + per_page - 1) // per_page
    
    tasks = query.order_by(DriverJobOrders.jadwal_jemput.asc()).offset((page - 1) * per_page).limit(per_page).all()
    
    result = []
    for t in tasks:
        kendaraan_name = ""
        plat_nomor = ""
        if t.p2h and t.p2h.kendaraan:
            kendaraan_name = t.p2h.kendaraan.nama_kendaraan
            plat_nomor = t.p2h.kendaraan.plat_nomor
            
        result.append({
            "id": t.id,
            "nama_tamu": t.nama_tamu,
            "tujuan_perjalanan": t.tujuan_perjalanan,
            "lokasi_jemput": t.lokasi_jemput,
            "lokasi_tujuan": t.lokasi_tujuan,
            "jadwal_jemput": str(t.jadwal_jemput) if t.jadwal_jemput else None,
            "status": t.status,
            "kendaraan_name": kendaraan_name,
            "plat_nomor": plat_nomor
        })
        
    return {
        "status": True,
        "message": "My Tasks",
        "data": result,
        "meta": {
            "current_page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages
        }
    }

@router_android.put("/{id}/status")
def update_android_task_status(
    id: int,
    status: str = Form(...),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    t = db.query(DriverJobOrders).filter(DriverJobOrders.id == id, DriverJobOrders.user_id == current_user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan atau bukan milik Anda")
        
    valid_status = ['ASSIGNED', 'ON_THE_WAY_PICKUP', 'PICKED_UP', 'COMPLETED', 'CANCELED']
    if status not in valid_status:
        raise HTTPException(status_code=400, detail="Status tidak valid")
        
    t.status = status
    t.updated_at = datetime.datetime.now()
    
    if status == 'ON_THE_WAY_PICKUP' and not t.waktu_mulai:
        t.waktu_mulai = datetime.datetime.now()
    elif status == 'COMPLETED' and not t.waktu_sampai_tujuan:
        t.waktu_sampai_tujuan = datetime.datetime.now()
        
    db.commit()
    return {"status": True, "message": "Status berhasil diupdate", "data": {"id": t.id, "status": t.status}}

@router_android.post("/{id}/complete")
def complete_android_task(
    id: int,
    odometer_akhir_tugas: int = Form(...),
    keterangan_selesai: str = Form(None),
    foto_odometer_akhir: UploadFile = File(None),
    current_user: Users = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    t = db.query(DriverJobOrders).filter(DriverJobOrders.id == id, DriverJobOrders.user_id == current_user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task tidak ditemukan atau bukan milik Anda")
        
    foto_path = None
    if foto_odometer_akhir:
        ext = foto_odometer_akhir.filename.split('.')[-1]
        filename = f"{secrets.token_hex(8)}.{ext}"
        upload_dir = Path("/var/www/appPatrol-python/public/uploads/job_orders")
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / filename
        
        with open(file_path, "wb") as buffer:
            buffer.write(foto_odometer_akhir.file.read())
            
        foto_path = f"uploads/job_orders/{filename}"

    t.odometer_akhir_tugas = odometer_akhir_tugas
    t.keterangan_selesai = keterangan_selesai
    if foto_path:
        t.foto_odometer_akhir = foto_path
        
    t.status = 'COMPLETED'
    t.waktu_sampai_tujuan = datetime.datetime.now()
    t.updated_at = datetime.datetime.now()
    
    db.commit()
    return {"status": True, "message": "Task berhasil diselesaikan", "data": {"id": t.id}}

