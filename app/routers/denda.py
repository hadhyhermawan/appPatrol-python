from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Denda
from pydantic import BaseModel
from typing import List

router = APIRouter(
    prefix="/api/denda",
    tags=["Denda"],
    responses={404: {"description": "Not found"}},
)

class DendaCreate(BaseModel):
    dari: int
    sampai: int
    denda: int

class DendaUpdate(BaseModel):
    dari: int
    sampai: int
    denda: int

class DendaResponse(BaseModel):
    id: int
    dari: int
    sampai: int
    denda: int

    class Config:
        from_attributes = True

@router.get("", response_model=List[DendaResponse])
async def get_all_denda(db: Session = Depends(get_db)):
    denda_list = db.query(Denda).order_by(Denda.id).all()
    return denda_list

@router.post("", response_model=DendaResponse)
async def create_denda(denda_data: DendaCreate, db: Session = Depends(get_db)):
    # Validate overlaps if necessary, but following simple Laravel structure
    new_denda = Denda(
        dari=denda_data.dari,
        sampai=denda_data.sampai,
        denda=denda_data.denda
    )
    db.add(new_denda)
    db.commit()
    db.refresh(new_denda)
    return new_denda

@router.put("/{denda_id}", response_model=DendaResponse)
async def update_denda(denda_id: int, denda_data: DendaUpdate, db: Session = Depends(get_db)):
    existing = db.query(Denda).filter(Denda.id == denda_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Denda tidak ditemukan")
    
    existing.dari = denda_data.dari
    existing.sampai = denda_data.sampai
    existing.denda = denda_data.denda
    
    db.commit()
    db.refresh(existing)
    return existing

@router.delete("/{denda_id}")
async def delete_denda(denda_id: int, db: Session = Depends(get_db)):
    existing = db.query(Denda).filter(Denda.id == denda_id).first()
    if not existing:
        raise HTTPException(status_code=404, detail="Denda tidak ditemukan")
    
    db.delete(existing)
    db.commit()
    return {"message": "Denda berhasil dihapus"}
