from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.compliance import UserAgreement
from app.routers.auth_legacy import get_current_user_sanctum

router_android = APIRouter(
    prefix="/api/android/compliance",
    tags=["Compliance (Android)"]
)

router_admin = APIRouter(
    prefix="/api/compliance",
    tags=["Compliance (Admin)"]
)

class AgreementRequest(BaseModel):
    terms_version: str
    privacy_version: str
    device_info: Optional[str] = None

class AgreementResponse(BaseModel):
    message: str
    agreed_at: str

@router_android.post("/agreement", response_model=AgreementResponse)
def create_agreement(
    request: AgreementRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_sanctum) # Legacy Sanctum Auth for Mobile
):
    try:
        # Check if identical agreement already exists
        existing = db.query(UserAgreement).filter(
            UserAgreement.user_id == current_user.id,
            UserAgreement.terms_version == request.terms_version,
            UserAgreement.privacy_version == request.privacy_version
        ).first()

        if existing:
            # Update device info if it changed
            if request.device_info and existing.device_info != request.device_info:
                existing.device_info = request.device_info
                db.commit()
            
            return AgreementResponse(
                message="Agreement already recorded",
                agreed_at=existing.agreed_at.isoformat() if existing.agreed_at else ""
            )

        new_agreement = UserAgreement(
            user_id=current_user.id,
            terms_version=request.terms_version,
            privacy_version=request.privacy_version,
            device_info=request.device_info
        )
        db.add(new_agreement)
        db.commit()
        db.refresh(new_agreement)

        return AgreementResponse(
            message="Agreement recorded successfully",
            agreed_at=new_agreement.agreed_at.isoformat() if new_agreement.agreed_at else ""
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record agreement: {str(e)}")

from sqlalchemy import text
from app.core.permissions import get_current_user, CurrentUser

@router_admin.get("/agreements")
def get_user_agreements(
    department_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    position_id: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    sql = """
        SELECT ua.id, ua.terms_version, ua.privacy_version, ua.device_info, ua.agreed_at,
               u.name as user_name, u.email as user_email, u.username as user_nik,
               d.nama_dept as department_name, c.nama_cabang as branch_name, j.nama_jabatan as position_name
        FROM user_agreements ua
        JOIN users u ON ua.user_id = u.id
        LEFT JOIN users_karyawan uk ON u.id = uk.id_user
        LEFT JOIN karyawan k ON (uk.nik = k.nik OR u.username = k.nik)
        LEFT JOIN departemen d ON k.kode_dept = d.kode_dept
        LEFT JOIN cabang c ON k.kode_cabang = c.kode_cabang
        LEFT JOIN jabatan j ON k.kode_jabatan = j.kode_jabatan
        WHERE 1=1
    """
    params = {}
    
    if department_id:
        sql += " AND k.kode_dept = :department_id"
        params['department_id'] = department_id
    if branch_id:
        sql += " AND k.kode_cabang = :branch_id"
        params['branch_id'] = branch_id
    if position_id:
        sql += " AND k.kode_jabatan = :position_id"
        params['position_id'] = position_id
    if search:
        sql += " AND (u.name LIKE :search OR u.username LIKE :search OR u.email LIKE :search)"
        params['search'] = f"%{search}%"
        
    sql += " ORDER BY ua.agreed_at DESC"
    
    agreements = db.execute(text(sql), params).fetchall()
    
    return [
        {
            "id": a.id,
            "user_name": a.user_name,
            "user_email": a.user_email or a.user_nik,
            "department": a.department_name or "-",
            "branch": a.branch_name or "-",
            "position": a.position_name or "-",
            "terms_version": a.terms_version,
            "privacy_version": a.privacy_version,
            "device_info": a.device_info,
            "agreed_at": a.agreed_at.isoformat() if a.agreed_at else None
        }
        for a in agreements
    ]
