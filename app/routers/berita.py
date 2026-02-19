from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc, text, or_, and_
from app.database import get_db
from app.models.models import Berita, Departemen, Users, Karyawan, Userkaryawan
from typing import List, Optional, Any
from pydantic import BaseModel
from datetime import datetime
import shutil
import os
import uuid
import html
import re
from app.routers.master import get_full_image_url
from app.core.permissions import get_current_user, CurrentUser

router = APIRouter(
    prefix="/api/berita",
    tags=["Berita"]
)

# --- DTOs matching Laravel Response ---

class BeritaDTO(BaseModel):
    id: int
    judul: str
    isi: str
    foto_url: Optional[str]
    created_by: Optional[int]
    created_by_name: Optional[str] = None
    kode_dept_target: Optional[str]
    nama_dept_target: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        orm_mode = True

class PaginationMeta(BaseModel):
    current_page: int
    last_page: int
    per_page: int
    total: int

class BeritaFilters(BaseModel):
    judul: Optional[str] = None
    kode_dept_target: Optional[str] = None

class BeritaPermissions(BaseModel):
    can_create: bool
    can_edit: bool
    can_delete: bool

class BeritaListResponse(BaseModel):
    success: bool
    data: List[BeritaDTO]
    pagination: PaginationMeta
    filters: BeritaFilters
    permissions: BeritaPermissions

# --- Utility Functions ---

def strip_tags(text: str) -> str:
    if not text:
        return ""
    # Decode HTML entities
    decoded = html.unescape(text)
    # Remove HTML tags using regex
    clean = re.compile('<.*?>')
    return re.sub(clean, '', decoded)

# --- Endpoints ---

@router.get("", response_model=BeritaListResponse)
@router.get("/list", response_model=BeritaListResponse)
async def get_berita_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    judul: Optional[str] = None,
    kode_dept_target: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check permissions for response
        can_create = current_user.has_permission("berita.create")
        can_edit = current_user.has_permission("berita.edit")
        can_delete = current_user.has_permission("berita.delete")

        query = db.query(Berita)
        
        # Implement Role Check (Karyawan vs Admin)
        is_karyawan = any(role["name"] == "karyawan" for role in current_user.roles)
        
        if is_karyawan:
            # Get user's department
            # SQLAlchemy Core query for simple join and select
            stmt = db.query(Karyawan.kode_dept).join(
                Userkaryawan, 
                Userkaryawan.nik == Karyawan.nik
            ).filter(
                Userkaryawan.id_user == current_user.id
            )
            kode_dept_user = stmt.scalar()
            
            # Filter: Global news (kode_dept_target is NULL) OR My Dept news
            if kode_dept_user:
                query = query.filter(
                    or_(
                        Berita.kode_dept_target == None,
                        Berita.kode_dept_target == kode_dept_user
                    )
                )
            else:
                query = query.filter(Berita.kode_dept_target == None)
        else:
            # Admin logic
            if kode_dept_target:
                if kode_dept_target == 'all':
                    query = query.filter(Berita.kode_dept_target == None)
                else:
                    query = query.filter(Berita.kode_dept_target == kode_dept_target)

        # Search by Judul
        if judul:
            query = query.filter(Berita.judul.like(f"%{judul}%"))
            
        # Order by created_at desc
        query = query.order_by(desc(Berita.created_at))
        
        # Pagination
        total_items = query.count()
        import math
        total_pages = math.ceil(total_items / per_page)
        
        results = query.offset((page - 1) * per_page).limit(per_page).all()
        
        data_list = []
        for row in results:
            author_name = row.users.name if row.users else None
            dept_name = row.departemen.nama_dept if row.departemen else None
            
            # Format date "12 Feb 2026 12:22"
            created_at_fmt = row.created_at.strftime("%d %b %Y %H:%M") if row.created_at else ""
            updated_at_fmt = row.updated_at.strftime("%d %b %Y %H:%M") if row.updated_at else ""
            
            # Process isi: strip tags and limit 200 chars for list view
            clean_isi = strip_tags(row.isi)
            isi_preview = (clean_isi[:200] + '...') if len(clean_isi) > 200 else clean_isi
            
            # Foto URL
            foto_url = None
            if row.foto:
                 foto_url = get_full_image_url(row.foto, "storage/uploads/berita")
            
            # Create DTO
            dto = BeritaDTO(
                id=row.id,
                judul=html.unescape(row.judul) if row.judul else "",
                isi=isi_preview,
                foto_url=foto_url,
                created_by=row.created_by,
                created_by_name=author_name,
                kode_dept_target=row.kode_dept_target,
                nama_dept_target=dept_name,
                created_at=created_at_fmt,
                updated_at=updated_at_fmt
            )
            data_list.append(dto)
            
        return BeritaListResponse(
            success=True,
            data=data_list,
            pagination=PaginationMeta(
                current_page=page,
                last_page=total_pages,
                per_page=per_page,
                total=total_items
            ),
            filters=BeritaFilters(
                judul=judul,
                kode_dept_target=kode_dept_target
            ),
            permissions=BeritaPermissions(
                can_create=can_create,
                can_edit=can_edit,
                can_delete=can_delete
            )
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{id}")
async def get_berita_detail(
    id: int,
    raw: bool = Query(False),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    berita = db.query(Berita).filter(Berita.id == id).first()
    if not berita:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
    # Check access for Karyawan
    is_karyawan = any(role["name"] == "karyawan" for role in current_user.roles)
    if is_karyawan:
        # Get department
        stmt = db.query(Karyawan.kode_dept).join(
            Userkaryawan,
            Userkaryawan.nik == Karyawan.nik
        ).filter(
            Userkaryawan.id_user == current_user.id
        )
        kode_dept_user = stmt.scalar()
        
        # If news is targeted to a dept, check if user belongs to it
        if berita.kode_dept_target and berita.kode_dept_target != kode_dept_user:
             raise HTTPException(status_code=404, detail="Data tidak ditemukan")

    # Content processing
    if raw:
        if not current_user.has_permission('berita.edit'):
            raise HTTPException(status_code=403, detail="Forbidden")
        isi_html = berita.isi
    else:
        # Simple sanitization
        isi_html = html.unescape(berita.isi)
        # remove scripts
        isi_html = re.sub(r'<script.*?>.*?</script>', '', isi_html, flags=re.DOTALL)
        # remove event handlers
        isi_html = re.sub(r' on\w+="[^"]*"', '', isi_html)

    # Foto
    foto_url = None
    if berita.foto:
         foto_url = get_full_image_url(berita.foto, "storage/uploads/berita")
         
    author_name = berita.users.name if berita.users else None
    dept_name = berita.departemen.nama_dept if berita.departemen else None
    
    return {
        "success": True,
        "data": {
            "id": berita.id,
            "judul": html.unescape(berita.judul) if berita.judul else "",
            "isi": isi_html,
            "foto_url": foto_url,
            "created_by": berita.created_by,
            "created_by_name": author_name,
            "kode_dept_target": berita.kode_dept_target,
            "nama_dept_target": dept_name,
            "created_at": berita.created_at.strftime("%d %b %Y %H:%M") if berita.created_at else "",
            "updated_at": berita.updated_at.strftime("%d %b %Y %H:%M") if berita.updated_at else ""
        }
    }

@router.post("")
async def create_berita(
    judul: str = Form(...),
    isi: str = Form(...),
    kode_dept_target: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.has_permission("berita.create"):
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        foto_path = None
        if foto:
            # Upload directory (Shared with Laravel)
            upload_dir = "/var/www/appPatrol/storage/app/public/uploads/berita"
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate unique filename
            file_extension = os.path.splitext(foto.filename)[1]
            tanggal = datetime.now().strftime("%Y-%m-%d")
            username_slug = re.sub(r'[^a-zA-Z0-9]', '_', current_user.username)
            unique_str = str(uuid.uuid4())[:6]
            
            nama_foto = f"{tanggal}_{username_slug}_{unique_str}{file_extension}"
            file_path = os.path.join(upload_dir, nama_foto)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(foto.file, buffer)
                
            foto_path = nama_foto

        new_berita = Berita(
            judul=judul,
            isi=isi,
            kode_dept_target=kode_dept_target if kode_dept_target not in ("null", "", "undefined") else None,
            foto=foto_path,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            created_by=current_user.id
        )
        
        db.add(new_berita)
        db.commit()
        db.refresh(new_berita)
        
        return {
            "success": True, 
            "message": "Berita berhasil ditambahkan", 
            "data": new_berita
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{id}")
async def update_berita(
    id: int,
    judul: str = Form(...),
    isi: str = Form(...),
    kode_dept_target: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.has_permission("berita.edit"):
        raise HTTPException(status_code=403, detail="Forbidden")

    berita = db.query(Berita).filter(Berita.id == id).first()
    if not berita:
        raise HTTPException(status_code=404, detail="Berita tidak ditemukan")

    try:
        # Handle Photo Update
        if foto:
            # 1. Delete old photo if exists
            if berita.foto:
                old_path = f"/var/www/appPatrol/storage/app/public/uploads/berita/{berita.foto}"
                if os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except:
                        pass
            
            # 2. Save new photo
            upload_dir = "/var/www/appPatrol/storage/app/public/uploads/berita"
            os.makedirs(upload_dir, exist_ok=True)
            
            file_extension = os.path.splitext(foto.filename)[1]
            tanggal = datetime.now().strftime("%Y-%m-%d")
            username_slug = re.sub(r'[^a-zA-Z0-9]', '_', current_user.username)
            unique_str = str(uuid.uuid4())[:6]
            
            nama_foto = f"{tanggal}_{username_slug}_{unique_str}{file_extension}"
            file_path = os.path.join(upload_dir, nama_foto)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(foto.file, buffer)
            
            berita.foto = nama_foto # Save filename only

        # Update other fields
        berita.judul = judul
        berita.isi = isi
        berita.kode_dept_target = kode_dept_target if kode_dept_target not in ("null", "", "undefined") else None
        # berita.updated_at = datetime.now() # SQLAlchemy usually handles this or use explicit set if not auto-updated
        berita.updated_at = datetime.now()
        
        db.commit()
        db.refresh(berita)
        
        return {
            "success": True, 
            "message": "Berita berhasil diperbarui",
            "data": {
                "id": berita.id
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{id}")
async def delete_berita(
    id: int, 
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if not current_user.has_permission('berita.delete'):
             raise HTTPException(status_code=403, detail="Forbidden")

        item = db.query(Berita).filter(Berita.id == id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Berita tidak ditemukan")
            
        # Delete file
        if item.foto:
            try:
                # Assuming uploads/berita is relative to current working dir
                # Delete from shared storage
                storage_path = f"/var/www/appPatrol/storage/app/public/uploads/berita/{item.foto}"
                if os.path.exists(storage_path):
                    os.remove(storage_path)
            except:
                pass
                
        db.delete(item)
        db.commit()
        return {"success": True, "message": "Berita berhasil dihapus"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
