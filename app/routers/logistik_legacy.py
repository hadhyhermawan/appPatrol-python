from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc
import shutil
import os
import uuid

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import Tamu, Barang, BarangMasuk, BarangKeluar

router = APIRouter(
    prefix="/api/android",
    tags=["Logistik Legacy"],
)

STORAGE_TAMU = "/var/www/appPatrol/storage/app/public/tamu"
STORAGE_BARANG = "/var/www/appPatrol/storage/app/public/barang"
os.makedirs(STORAGE_TAMU, exist_ok=True)
os.makedirs(STORAGE_BARANG, exist_ok=True)

# --- TAMU ---

@router.get("/tamu")
async def list_tamu(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    # Get active or recent tamu
    tamus = db.query(Tamu).order_by(desc(Tamu.jam_masuk)).limit(limit).all()
    
    data = []
    for t in tamus:
        data.append({
            "id_tamu": t.id_tamu,
            "nama": t.nama,
            "alamat": t.alamat,
            "perusahaan": t.perusahaan,
            "bertemu_dengan": t.bertemu_dengan,
            "keperluan": t.keperluan,
            "jam_masuk": str(t.jam_masuk) if t.jam_masuk else None,
            "jam_keluar": str(t.jam_keluar) if t.jam_keluar else None,
            "foto": t.foto,
            "foto_keluar": t.foto_keluar,
            "no_pol": t.no_pol,
            "jenis_kendaraan": t.jenis_kendaraan
        })
    return {"status": True, "data": data}

@router.post("/tamu/store")
async def store_tamu(
    nama: str = Form(...),
    alamat: str = Form(""),
    jenis_id: str = Form(None, alias="jenisId"), # Handle camelCase
    no_telp: str = Form("", alias="noTelp"),
    perusahaan: str = Form(""),
    bertemu_dengan: str = Form("", alias="bertemuDengan"),
    dengan_perjanjian: str = Form("TIDAK", alias="dp"), # Repository sends 'dp'
    keperluan: str = Form(""),
    jenis_kendaraan: str = Form("PEJALAN KAKI", alias="jk"), # Repository sends 'jk' alias? Check logic.
    no_pol: str = Form("", alias="noPol"),
    foto: UploadFile = File(...),
    kode_jam_kerja: str = Form(None), 
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # Save Image
    filename = f"tamu_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}.jpg"
    path = os.path.join(STORAGE_TAMU, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(foto.file, buffer)
        
    new_tamu = Tamu(
        nama=nama,
        alamat=alamat,
        jenis_id=jenis_id,
        no_telp=no_telp,
        perusahaan=perusahaan,
        bertemu_dengan=bertemu_dengan,
        dengan_perjanjian=dengan_perjanjian,
        keperluan=keperluan,
        jenis_kendaraan=jenis_kendaraan, # Android 'jk' mapped to ?
        no_pol=no_pol,
        foto=f"tamu/{filename}",
        jam_masuk=datetime.now(),
        nik_satpam=user.nik
    )
    db.add(new_tamu)
    db.commit()
    db.refresh(new_tamu)
    
    return {"status": True, "message": "Tamu Berhasil Disimpan", "data": {"id_tamu": new_tamu.id_tamu}}

@router.post("/tamu/checkout/{id_tamu}") # Repository path param
async def checkout_tamu(
    id_tamu: int,
    jam_keluar: str = Form(None, alias="jamKeluar"), # From repo
    foto_keluar: UploadFile = File(None, alias="fotoKeluar"),
    kode_jam_kerja: str = Form(None),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    tamu = db.query(Tamu).filter(Tamu.id_tamu == id_tamu).first()
    if not tamu:
        raise HTTPException(404, "Data Tamu Tidak Ditemukan")
        
    if foto_keluar:
        filename = f"tamu_out_{id_tamu}_{uuid.uuid4().hex[:4]}.jpg"
        path = os.path.join(STORAGE_TAMU, filename)
        with open(path, "wb") as buffer:
            shutil.copyfileobj(foto_keluar.file, buffer)
        tamu.foto_keluar = f"tamu/{filename}"
        
    tamu.jam_keluar = datetime.now()
    tamu.nik_satpam_keluar = user.nik
    
    db.commit()
    return {"status": True, "message": "Checkout Berhasil"}

# --- BARANG ---
# MOVED TO app/routers/barang_legacy.py
