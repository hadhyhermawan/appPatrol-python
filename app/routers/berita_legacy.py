from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, text, or_
from typing import List, Optional

from app.database import get_db
from app.core.permissions import get_current_user, CurrentUser as CoreCurrentUser
from app.routers.berita import (
    BeritaListResponse, 
    get_berita_list as original_get_berita_list, 
    get_berita_detail as original_get_berita_detail
)

router = APIRouter(
    prefix="/api/android",
    tags=["Berita Legacy"],
)

# Support multiple potentially used endpoints.
@router.get("/berita/list", response_model=BeritaListResponse)
@router.get("/berita", response_model=BeritaListResponse)
async def get_android_berita_list(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1),
    judul: Optional[str] = None,
    kode_dept_target: Optional[str] = None,
    current_user: CoreCurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Proxy to the main Berita implementation.
    The main implementation handles response formatting matching Laravel.
    """
    return await original_get_berita_list(
        page=page,
        per_page=per_page,
        judul=judul,
        kode_dept_target=kode_dept_target,
        current_user=current_user,
        db=db
    )

@router.get("/berita/detail/{id}")
@router.get("/berita/{id}")
async def get_android_berita_detail(
    id: int,
    current_user: CoreCurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return await original_get_berita_detail(
        id=id,
        raw=False, # Android never needs raw HTML editing
        current_user=current_user,
        db=db
    )

@router.get("/notifications")
async def get_notifications():
    # Stub for notifications
    return {"status": True, "data": []}
