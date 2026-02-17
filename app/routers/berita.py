from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.database import get_db
from app.models.models import Berita, Departemen, Users
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import shutil
import os
import uuid

router = APIRouter(
    prefix="/api/berita",
    tags=["Berita"]
)

class BeritaDTO(BaseModel):
    id: int
    judul: str
    isi: str
    foto: Optional[str]
    kode_dept_target: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    nama_dept_target: Optional[str] = None
    author: Optional[str] = None

    class Config:
        orm_mode = True

class PaginationMeta(BaseModel):
    total_items: int
    total_pages: int
    current_page: int
    per_page: int

class BeritaListResponse(BaseModel):
    status: bool
    data: List[BeritaDTO]
    meta: Optional[PaginationMeta] = None

@router.get("", response_model=BeritaListResponse)
async def get_berita_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Berita)
        
        if search:
            query = query.filter(Berita.judul.like(f"%{search}%"))
            
        query = query.order_by(desc(Berita.created_at))
        
        # Pagination
        total_items = query.count()
        import math
        total_pages = math.ceil(total_items / per_page)
        
        results = query.offset((page - 1) * per_page).limit(per_page).all()
        
        data_list = []
        for row in results:
            author_name = row.users.name if row.users else "Unknown"
            dept_name = row.departemen.nama_dept if row.departemen else "Semua Departemen"
            
            data_list.append(BeritaDTO(
                id=row.id,
                judul=row.judul,
                isi=row.isi,
                foto=row.foto,
                kode_dept_target=row.kode_dept_target,
                created_at=row.created_at,
                updated_at=row.updated_at,
                nama_dept_target=dept_name,
                author=author_name
            ))
            
        return BeritaListResponse(
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
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def create_berita(
    judul: str = Form(...),
    isi: str = Form(...),
    kode_dept_target: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    try:
        foto_path = None
        if foto:
            # Upload directory
            upload_dir = "uploads/berita"
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate unique filename
            file_extension = os.path.splitext(foto.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(foto.file, buffer)
                
            foto_path = unique_filename

        new_berita = Berita(
            judul=judul,
            isi=isi,
            kode_dept_target=kode_dept_target if kode_dept_target != "null" and kode_dept_target != "" else None,
            foto=foto_path,
            created_at=datetime.now(),
            updated_at=datetime.now()
            # created_by hardcoded for now or get from token
        )
        
        db.add(new_berita)
        db.commit()
        db.refresh(new_berita)
        
        return {"status": True, "message": "Berita berhasil dibuat"}
    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
async def delete_berita(id: int, db: Session = Depends(get_db)):
    try:
        item = db.query(Berita).filter(Berita.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Berita tidak ditemukan")
            
        # Optional: Delete file
        if item.foto:
            try:
                os.remove(f"uploads/berita/{item.foto}")
            except:
                pass
                
        db.delete(item)
        db.commit()
        return {"status": True, "message": "Berita berhasil dihapus"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
