from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.models import PresensiJamkerjaBydept, PresensiJamkerja, Cabang, Departemen, PresensiJamkerjaByDeptDetail
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(
    prefix="/api/settings/jam-kerja-dept",
    tags=["Jam Kerja Dept"],
    responses={404: {"description": "Not found"}},
)

# DTOs
class JamKerjaDeptDTO(BaseModel):
    kode_jk_dept: str
    kode_cabang: str
    kode_dept: str
    nama_cabang: Optional[str] = None
    nama_dept: Optional[str] = None
    
    class Config:
        from_attributes = True

class JamKerjaDeptDetailDTO(BaseModel):
    kode_jk_dept: str
    hari: str
    kode_jam_kerja: str

class CreateJamKerjaDeptDTO(BaseModel):
    kode_cabang: str
    kode_dept: str
    hari: List[str]
    kode_jam_kerja: List[str]

class UpdateJamKerjaDeptDTO(BaseModel):
    hari: List[str]
    kode_jam_kerja: List[str]

@router.get("")
async def get_jam_kerja_dept(
    page: int = 1,
    limit: int = 15,
    kode_cabang: Optional[str] = None,
    db: Session = Depends(get_db)
):
    offset = (page - 1) * limit
    
    query = db.query(PresensiJamkerjaBydept, Cabang.nama_cabang, Departemen.nama_dept)\
        .join(Cabang, PresensiJamkerjaBydept.kode_cabang == Cabang.kode_cabang)\
        .join(Departemen, PresensiJamkerjaBydept.kode_dept == Departemen.kode_dept)
    
    if kode_cabang:
        query = query.filter(PresensiJamkerjaBydept.kode_cabang == kode_cabang)
        
    total = query.count()
    results = query.offset(offset).limit(limit).all()
    
    data = []
    for row in results:
        item = row[0]
        data.append({
            "kode_jk_dept": item.kode_jk_dept,
            "kode_cabang": item.kode_cabang,
            "kode_dept": item.kode_dept,
            "nama_cabang": row[1],
            "nama_dept": row[2]
        })
        
    return {
        "data": data,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
            "last_page": (total + limit - 1) // limit
        }
    }

@router.get("/options/jam-kerja")
async def get_jam_kerja_options(db: Session = Depends(get_db)):
    return db.query(PresensiJamkerja).order_by(PresensiJamkerja.kode_jam_kerja).all()

@router.post("")
async def create_jam_kerja_dept(payload: CreateJamKerjaDeptDTO, db: Session = Depends(get_db)):
    # Check existing
    existing = db.query(PresensiJamkerjaBydept).filter(
        PresensiJamkerjaBydept.kode_cabang == payload.kode_cabang,
        PresensiJamkerjaBydept.kode_dept == payload.kode_dept
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Data Jam Kerja Sudah Ada")
    
    kode_jk_dept = f"J{payload.kode_cabang}{payload.kode_dept}"
    
    try:
        new_jk_dept = PresensiJamkerjaBydept(
            kode_jk_dept=kode_jk_dept,
            kode_cabang=payload.kode_cabang,
            kode_dept=payload.kode_dept,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        db.add(new_jk_dept)
        db.flush() 
        
        # Insert details
        for i, hari in enumerate(payload.hari):
            if i < len(payload.kode_jam_kerja) and payload.kode_jam_kerja[i]:
                new_detail = PresensiJamkerjaByDeptDetail(
                    kode_jk_dept=kode_jk_dept,
                    hari=hari,
                    kode_jam_kerja=payload.kode_jam_kerja[i],
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(new_detail)
                
        db.commit()
        return {"message": "Data Berhasil Disimpan"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{kode_jk_dept}")
async def get_jam_kerja_dept_detail(kode_jk_dept: str, db: Session = Depends(get_db)):
    jk_dept = db.query(PresensiJamkerjaBydept, Cabang.nama_cabang, Departemen.nama_dept)\
        .join(Cabang, PresensiJamkerjaBydept.kode_cabang == Cabang.kode_cabang)\
        .join(Departemen, PresensiJamkerjaBydept.kode_dept == Departemen.kode_dept)\
        .filter(PresensiJamkerjaBydept.kode_jk_dept == kode_jk_dept)\
        .first()
        
    if not jk_dept:
        raise HTTPException(status_code=404, detail="Data not found")
        
    details_query = db.query(PresensiJamkerjaByDeptDetail).filter(
        PresensiJamkerjaByDeptDetail.kode_jk_dept == kode_jk_dept
    ).all()
    
    # Map details to simple dictionary for easier frontend consumption {day: kode_jam_kerja}
    details_map = {}
    for d in details_query:
        details_map[d.hari] = d.kode_jam_kerja
        
    return {
        "header": {
            "kode_jk_dept": jk_dept[0].kode_jk_dept,
            "kode_cabang": jk_dept[0].kode_cabang,
            "kode_dept": jk_dept[0].kode_dept,
            "nama_cabang": jk_dept[1],
            "nama_dept": jk_dept[2]
        },
        "details": details_map
    }

@router.put("/{kode_jk_dept}")
async def update_jam_kerja_dept(kode_jk_dept: str, payload: UpdateJamKerjaDeptDTO, db: Session = Depends(get_db)):
    jk_dept = db.query(PresensiJamkerjaBydept).filter(PresensiJamkerjaBydept.kode_jk_dept == kode_jk_dept).first()
    if not jk_dept:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        # Delete existing details
        db.query(PresensiJamkerjaByDeptDetail).filter(
            PresensiJamkerjaByDeptDetail.kode_jk_dept == kode_jk_dept
        ).delete()
        
        # Insert new details
        for i, hari in enumerate(payload.hari):
             if i < len(payload.kode_jam_kerja) and payload.kode_jam_kerja[i]:
                new_detail = PresensiJamkerjaByDeptDetail(
                    kode_jk_dept=kode_jk_dept,
                    hari=hari,
                    kode_jam_kerja=payload.kode_jam_kerja[i],
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(new_detail)
        
        jk_dept.updated_at = datetime.now()
        db.commit()
        return {"message": "Data Berhasil Diupdate"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{kode_jk_dept}")
async def delete_jam_kerja_dept(kode_jk_dept: str, db: Session = Depends(get_db)):
    jk_dept = db.query(PresensiJamkerjaBydept).filter(PresensiJamkerjaBydept.kode_jk_dept == kode_jk_dept).first()
    if not jk_dept:
        raise HTTPException(status_code=404, detail="Data not found")
        
    try:
        # Details should be deleted by cascade, but explicit is safer if not configured in DB
        # Check model definition for cascade, confirmed in previous steps
        
        db.delete(jk_dept)
        db.commit()
        return {"message": "Data Berhasil Dihapus"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
