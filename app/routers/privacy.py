from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.database import get_db
from app.models.privacy import PrivacyPolicy
from app.core.permissions import get_current_user, CurrentUser, require_permission_dependency
from app.routers.auth_legacy import get_current_user_sanctum

router = APIRouter(
    prefix="/api/privacy",
    tags=["Privacy Policy"]
)

router_android = APIRouter(
    prefix="/api/android/privacy",
    tags=["Privacy Policy (Android)"]
)

class PrivacyBase(BaseModel):
    title: str
    content: str
    version: str
    is_active: bool = False

class PrivacyCreate(PrivacyBase):
    pass

class PrivacyUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None

class PrivacyResponse(PrivacyBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# GET active privacy policy for WEB (requires web authentication)
@router.get("/active", response_model=PrivacyResponse)
def get_active_privacy(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    privacy = db.query(PrivacyPolicy).filter(PrivacyPolicy.is_active == True).order_by(PrivacyPolicy.updated_at.desc()).first()
    if not privacy:
        raise HTTPException(status_code=404, detail="No active privacy policy found")
    return privacy

# GET active privacy policy for ANDROID (requires legacy/sanctum authentication)
@router_android.get("/active", response_model=PrivacyResponse)
def get_active_privacy_android(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_sanctum)
):
    privacy = db.query(PrivacyPolicy).filter(PrivacyPolicy.is_active == True).order_by(PrivacyPolicy.updated_at.desc()).first()
    if not privacy:
        raise HTTPException(status_code=404, detail="No active privacy policy found")
    return privacy

# GET all privacy policies for admin dashboard
@router.get("", response_model=List[PrivacyResponse])
def get_all_privacies(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user) # Ideally specific permission like Depends(require_permission_dependency('privacy.view'))
):
    return db.query(PrivacyPolicy).order_by(PrivacyPolicy.updated_at.desc()).all()

# POST create new privacy policy
@router.post("", response_model=PrivacyResponse, status_code=status.HTTP_201_CREATED)
def create_privacy(
    privacy: PrivacyCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user) # Ideally specific permission
):
    if privacy.is_active:
        # Deactivate all others
        db.query(PrivacyPolicy).update({"is_active": False})
        
    db_privacy = PrivacyPolicy(**privacy.model_dump())
    db.add(db_privacy)
    db.commit()
    db.refresh(db_privacy)
    return db_privacy

# PUT update privacy policy
@router.put("/{privacy_id}", response_model=PrivacyResponse)
def update_privacy(
    privacy_id: int,
    privacy: PrivacyUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user) # Ideally specific permission
):
    db_privacy = db.query(PrivacyPolicy).filter(PrivacyPolicy.id == privacy_id).first()
    if not db_privacy:
        raise HTTPException(status_code=404, detail="Privacy policy not found")
        
    update_data = privacy.model_dump(exclude_unset=True)
    
    if "is_active" in update_data and update_data["is_active"]:
        # Deactivate all others
        db.query(PrivacyPolicy).filter(PrivacyPolicy.id != privacy_id).update({"is_active": False})
        
    for key, value in update_data.items():
        setattr(db_privacy, key, value)
        
    db.commit()
    db.refresh(db_privacy)
    return db_privacy

# DELETE privacy policy
@router.delete("/{privacy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_privacy(
    privacy_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user) # Ideally specific permission
):
    db_privacy = db.query(PrivacyPolicy).filter(PrivacyPolicy.id == privacy_id).first()
    if not db_privacy:
        raise HTTPException(status_code=404, detail="Privacy policy not found")
        
    db.delete(db_privacy)
    db.commit()
    return None
