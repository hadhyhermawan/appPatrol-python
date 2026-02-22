from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.terms import TermsAndConditions
from app.core.permissions import get_current_user, CurrentUser
from app.routers.auth_legacy import get_current_user_sanctum

router = APIRouter(
    prefix="/api/terms",
    tags=["Terms and Conditions"]
)

router_android = APIRouter(
    prefix="/api/android/terms",
    tags=["Terms and Conditions (Android)"]
)

class TermsBase(BaseModel):
    title: str
    content: str
    version: str
    is_active: bool = False

class TermsCreate(TermsBase):
    pass

class TermsUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    version: Optional[str] = None
    is_active: Optional[bool] = None

class TermsResponse(TermsBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# GET active terms for WEB (requires web authentication)
@router.get("/active", response_model=TermsResponse)
def get_active_terms(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    terms = db.query(TermsAndConditions).filter(TermsAndConditions.is_active == True).order_by(TermsAndConditions.updated_at.desc()).first()
    if not terms:
        raise HTTPException(status_code=404, detail="No active terms and conditions found")
    return terms

# GET active terms for ANDROID (requires legacy/sanctum authentication)
@router_android.get("/active", response_model=TermsResponse)
def get_active_terms_android(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user_sanctum)
):
    terms = db.query(TermsAndConditions).filter(TermsAndConditions.is_active == True).order_by(TermsAndConditions.updated_at.desc()).first()
    if not terms:
        raise HTTPException(status_code=404, detail="No active terms and conditions found")
    return terms

# GET all terms for admin dashboard
@router.get("", response_model=List[TermsResponse])
def get_all_terms(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    # Only allow superadmin or specific roles if needed, simplified for now
    return db.query(TermsAndConditions).order_by(TermsAndConditions.created_at.desc()).all()

# POST create new terms (admin)
@router.post("", response_model=TermsResponse, status_code=status.HTTP_201_CREATED)
def create_terms(
    terms: TermsCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    if terms.is_active:
        # Deactivate all other terms
        db.query(TermsAndConditions).update({TermsAndConditions.is_active: False})
        
    db_terms = TermsAndConditions(**terms.model_dump())
    db.add(db_terms)
    db.commit()
    db.refresh(db_terms)
    return db_terms

# PUT update existing terms (admin)
@router.put("/{terms_id}", response_model=TermsResponse)
def update_terms(
    terms_id: int,
    terms_update: TermsUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    db_terms = db.query(TermsAndConditions).filter(TermsAndConditions.id == terms_id).first()
    if not db_terms:
        raise HTTPException(status_code=404, detail="Terms not found")

    update_data = terms_update.model_dump(exclude_unset=True)
    
    if update_data.get("is_active"):
        # Deactivate all other terms if this one is becoming active
        db.query(TermsAndConditions).filter(TermsAndConditions.id != terms_id).update({TermsAndConditions.is_active: False})

    for key, value in update_data.items():
        setattr(db_terms, key, value)

    db.commit()
    db.refresh(db_terms)
    return db_terms

# DELETE terms (admin)
@router.delete("/{terms_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_terms(
    terms_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    db_terms = db.query(TermsAndConditions).filter(TermsAndConditions.id == terms_id).first()
    if not db_terms:
        raise HTTPException(status_code=404, detail="Terms not found")

    db.delete(db_terms)
    db.commit()
    return None
