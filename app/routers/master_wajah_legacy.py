from fastapi import APIRouter, Depends, HTTPException, Body, Form, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
import shutil
import os
import uuid

from app.database import get_db
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from app.models.models import Karyawan, KaryawanWajah as Facerecognition

router = APIRouter(
    prefix="/api/android/masterwajah",
    tags=["Master Wajah Legacy"],
    responses={404: {"description": "Not found"}},
)

# Laravel Storage Path
STORAGE_BASE = "/var/www/appPatrol/storage/app/public/uploads/facerecognition"
# Ensure exist
os.makedirs(STORAGE_BASE, exist_ok=True)

@router.get("/{nik}")
async def get_wajah(
    nik: str,
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # 1. Check Karyawan
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if not karyawan:
        return {"success": False, "message": "Karyawan tidak ditemukan"} # Use success key to match PHP
        
    # 2. Get Faces
    faces = db.query(Facerecognition).filter(Facerecognition.nik == nik).all()
    
    # 3. Construct Data
    # Folder Logic: {nik}-{firstname} lowercase
    first_name = karyawan.nama_karyawan.split(' ')[0]
    folder_name = f"{nik}-{first_name}".lower()
    
    data = []
    base_url = f"https://frontend.k3guard.com/api-py/storage/uploads/facerecognition/{folder_name}"
    
    for f in faces:
        data.append({
            "id": f.id,
            "wajah": f.wajah,
            "url": f"{base_url}/{f.wajah}"
        })
        
    return {
        "success": True, 
        "nama": karyawan.nama_karyawan,
        "nik": nik,
        "data": data
    }

@router.post("/store")
async def store_master_wajah(
    nik: str = Form(...),
    images: List[UploadFile] = File(default=None, alias="images[]"),
    images_simple: List[UploadFile] = File(default=None, alias="images"),
    user: CurrentUser = Depends(get_current_user_data),
    db: Session = Depends(get_db)
):
    # Handle list alias
    uploaded_files = images if images else images_simple
    if not uploaded_files:
        from fastapi.responses import JSONResponse
        return JSONResponse(content={"success": False, "message": "Tidak ada gambar yang diupload"}, status_code=200)

    # 1. Validate Karyawan
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if not karyawan:
         from fastapi.responses import JSONResponse
         return JSONResponse(content={"success": False, "message": "Karyawan tidak ditemukan"}, status_code=200)
         
    # 2. Check Count
    count = db.query(Facerecognition).filter(Facerecognition.nik == nik).count()
    if count >= 5:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=200, content={
            "success": False,
            "message": "Anda sudah menambahkan wajah sebelumnya (Maks 5)"
        })
        
    # 3. Prepare Folder
    first_name = karyawan.nama_karyawan.split(' ')[0]
    folder_name = f"{nik}-{first_name}".lower()
    target_dir = os.path.join(STORAGE_BASE, folder_name)
    try:
        os.makedirs(target_dir, exist_ok=True)
        os.chmod(target_dir, 0o775) # Ensure permission
    except Exception as e:
        print(f"Error creating directory: {e}")
        # Continue implies it might work or fail next

    saved_files = []
    
    # Logic to get latest sequence if recreating or appending?
    # PHP code: $existingCount + 1. 
    # If we have 3 faces, next is 4.
    # But files need unique names?
    # We should query current max ID or verify file existence.
    # For now, simplistic count+1 approach as per PHP.
    
    current_count = count
    
    for img in uploaded_files:
        if current_count >= 5: break
        
        current_count += 1
        
        # PHP: {urutan}_{direction}.{ext}
        # Android sends 'master_face_0.jpg', etc.
        orig_name = img.filename
        direction = "front"
        
        # Simple extraction
        if orig_name and '.' in orig_name:
            name_part = os.path.splitext(orig_name)[0]
            if '_' in name_part:
                # e.g. master_face_0 -> face_0 or just 0?
                # PHP logic: $direction = pathinfo($original, PATHINFO_FILENAME) ?: 'front';
                # We'll just use the filename base as direction to be safe, or 'face'
                direction = name_part
            else:
                direction = name_part
        
        ext = os.path.splitext(orig_name)[1] if orig_name else ".jpg"
        if not ext: ext = ".jpg"
        
        new_filename = f"{current_count}_{direction}{ext}"
        target_path = os.path.join(target_dir, new_filename)
        
        # Save File
        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(img.file, buffer)
                
            # Save DB
            new_face = Facerecognition(
                nik=nik,
                wajah=new_filename
            )
            db.add(new_face)
            saved_files.append(new_filename)
        except Exception as e:
            print(f"Error saving file {new_filename}: {e}")
            continue
        
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"success": False, "message": f"Database Error: {str(e)}"})
    
    return {
        "success": True,
        "message": "Berhasil menyimpan data wajah"
    }
