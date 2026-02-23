from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, date
from app.database import get_db
from app.models.models import Violation
from app.routers.auth_legacy import get_current_user_data, CurrentUser
from sqlalchemy import desc
import os

router = APIRouter(
    prefix="/api/android/violations",
    tags=["Violations_Android"],
    responses={404: {"description": "Not found"}},
)

@router.get("/my")
def get_my_violations(
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user_data)
):
    nik = current_user.nik
    if not nik:
        raise HTTPException(status_code=400, detail="User NIK not found")

    query = db.query(Violation).filter(Violation.nik == nik)
    
    total = query.count()
    items = query.order_by(desc(Violation.tanggal_pelanggaran), desc(Violation.id)).offset((page - 1) * per_page).limit(per_page).all()

    result = []
    for item in items:
        foto_url = None
        if item.bukti_foto:
            foto_url = f"/storage/violations/{os.path.basename(item.bukti_foto)}"

        result.append({
            "id": item.id,
            "nik": item.nik,
            "tanggal_pelanggaran": item.tanggal_pelanggaran.isoformat() if item.tanggal_pelanggaran else None,
            "jenis_pelanggaran": item.jenis_pelanggaran,
            "keterangan": item.keterangan,
            "sanksi": item.sanksi,
            "status": item.status,
            "bukti_foto": foto_url,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "violation_type": item.violation_type,
            "source": item.source,
            "is_read": bool(getattr(item, 'is_read', 0))
        })

    return {
        "status": True,
        "message": "Success fetching violations",
        "data": result,
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page
        }
    }

@router.put("/{id}/read")
def mark_violation_as_read(
    id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user_data)
):
    nik = current_user.nik
    if not nik:
        raise HTTPException(status_code=400, detail="User NIK not found")

    violation = db.query(Violation).filter(Violation.id == id, Violation.nik == nik).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found or not owned by user")

    try:
        violation.is_read = 1
        db.commit()
        return {"status": True, "message": "Violation marked as read"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
