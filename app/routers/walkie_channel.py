from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models.models import WalkieChannels, WalkieChannelCabangs, Cabang, Departemen
from typing import List, Optional
from pydantic import BaseModel, constr
from datetime import datetime

router = APIRouter(
    prefix="/api/master/walkiechannel",
    tags=["Master Walkie Channel"],
    responses={404: {"description": "Not found"}},
)

# DTOs
class WalkieChannelBase(BaseModel):
    code: constr(to_upper=True, min_length=1, max_length=64, pattern=r"^[A-Z0-9_]+$")
    name: constr(max_length=100)
    dept_members: Optional[List[str]] = []
    active: int
    auto_join: int
    priority: int
    cabang_members: List[str]

class WalkieChannelCreate(WalkieChannelBase):
    pass

class WalkieChannelUpdate(WalkieChannelBase):
    pass

class WalkieChannelResponse(WalkieChannelBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class CabangDTO(BaseModel):
    kode_cabang: str
    nama_cabang: str
    class Config:
         from_attributes = True

class DepartemenDTO(BaseModel):
    kode_dept: str
    nama_dept: str
    class Config:
        from_attributes = True

@router.get("", response_model=dict)
async def get_walkie_channels(
    search: Optional[str] = None,
    rule_type: Optional[str] = None,
    active: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    query = db.query(WalkieChannels)

    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(
            WalkieChannels.code.ilike(search_term),
            WalkieChannels.name.ilike(search_term),
            WalkieChannels.rule_type.ilike(search_term),
            WalkieChannels.rule_value.ilike(search_term),
            WalkieChannels.dept_members.ilike(search_term)
        ))

    if rule_type:
        query = query.filter(WalkieChannels.rule_type == rule_type)

    if active is not None:
        is_active = active == '1' or active.lower() == 'true'
        query = query.filter(WalkieChannels.active == (1 if is_active else 0))

    query = query.order_by(WalkieChannels.code)
    
    total = query.count()
    offset = (page - 1) * limit
    channels = query.limit(limit).offset(offset).all()
    
    # Process channels to include cabang_members
    data = []
    for channel in channels:
        cabangs = db.query(WalkieChannelCabangs).filter(WalkieChannelCabangs.walkie_channel_id == channel.id).all()
        cabang_codes = [c.kode_cabang for c in cabangs]
        
        dept_members_list = []
        if channel.dept_members:
            dept_members_list = channel.dept_members.split(',')
            
        data.append({
            "id": channel.id,
            "code": channel.code,
            "name": channel.name,
            "rule_type": channel.rule_type,
            "rule_value": channel.rule_value, # This usually stores cabang codes CSV in Laravel implementation logic
            "dept_members": dept_members_list,
            "active": channel.active,
            "auto_join": channel.auto_join,
            "priority": channel.priority,
            "cabang_members": cabang_codes,
            "created_at": channel.created_at,
            "updated_at": channel.updated_at
        })
        
    return {
        "data": data,
        "meta": {
            "page": page,
            "limit": limit,
            "total": total
        }
    }

@router.post("", response_model=dict)
async def create_walkie_channel(item: WalkieChannelCreate, db: Session = Depends(get_db)):
    # Check if code exists
    existing = db.query(WalkieChannels).filter(WalkieChannels.code == item.code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Channel code {item.code} already exists")
    
    # Process members
    cabang_codes = sorted(list(set([c.upper() for c in item.cabang_members])))
    dept_codes = sorted(list(set([d.upper() for d in item.dept_members]))) if item.dept_members else []
    
    rule_value = ",".join(cabang_codes)
    dept_value = ",".join(dept_codes) if dept_codes else None
    
    new_channel = WalkieChannels(
        code=item.code,
        name=item.name,
        rule_type="cabang_group",
        rule_value=rule_value,
        active=item.active,
        auto_join=item.auto_join,
        priority=item.priority,
        dept_members=dept_value,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(new_channel)
    db.flush() # flush to get ID
    
    # Sync Cabangs
    for code in cabang_codes:
        db.add(WalkieChannelCabangs(
            walkie_channel_id=new_channel.id,
            kode_cabang=code,
            created_at=datetime.now(),
            updated_at=datetime.now()
        ))
        
    db.commit()
    return {"status": "success", "message": "Channel created successfully", "data": {"id": new_channel.id}}

@router.get("/{id}", response_model=dict)
async def get_walkie_channel(id: int, db: Session = Depends(get_db)):
    channel = db.query(WalkieChannels).filter(WalkieChannels.id == id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    cabangs = db.query(WalkieChannelCabangs).filter(WalkieChannelCabangs.walkie_channel_id == channel.id).all()
    cabang_codes = [c.kode_cabang for c in cabangs]
    
    dept_members_list = []
    if channel.dept_members:
        dept_members_list = channel.dept_members.split(',')
        
    data = {
        "id": channel.id,
        "code": channel.code,
        "name": channel.name,
        "rule_type": channel.rule_type,
        "rule_value": channel.rule_value,
        "dept_members": dept_members_list,
        "active": channel.active,
        "auto_join": channel.auto_join,
        "priority": channel.priority,
        "cabang_members": cabang_codes,
        "created_at": channel.created_at,
        "updated_at": channel.updated_at
    }
    
    return data

@router.put("/{id}", response_model=dict)
async def update_walkie_channel(id: int, item: WalkieChannelUpdate, db: Session = Depends(get_db)):
    channel = db.query(WalkieChannels).filter(WalkieChannels.id == id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
        
    # Check if code unique (excluding self)
    existing = db.query(WalkieChannels).filter(WalkieChannels.code == item.code).filter(WalkieChannels.id != id).first()
    if existing:
         raise HTTPException(status_code=400, detail=f"Channel code {item.code} already exists")
         
    cabang_codes = sorted(list(set([c.upper() for c in item.cabang_members])))
    dept_codes = sorted(list(set([d.upper() for d in item.dept_members]))) if item.dept_members else []
    
    rule_value = ",".join(cabang_codes)
    dept_value = ",".join(dept_codes) if dept_codes else None
    
    channel.code = item.code
    channel.name = item.name
    channel.rule_type = "cabang_group"
    channel.rule_value = rule_value
    channel.dept_members = dept_value
    channel.active = item.active
    channel.auto_join = item.auto_join
    channel.priority = item.priority
    channel.updated_at = datetime.now()
    
    # Sync Cabangs (Delete all then add)
    db.query(WalkieChannelCabangs).filter(WalkieChannelCabangs.walkie_channel_id == id).delete()
    
    for code in cabang_codes:
        db.add(WalkieChannelCabangs(
            walkie_channel_id=channel.id,
            kode_cabang=code,
            created_at=datetime.now(),
            updated_at=datetime.now()
        ))
        
    db.commit()
    return {"status": "success", "message": "Channel updated successfully"}

@router.delete("/{id}", response_model=dict)
async def delete_walkie_channel(id: int, db: Session = Depends(get_db)):
    channel = db.query(WalkieChannels).filter(WalkieChannels.id == id).first()
    if not channel:
         raise HTTPException(status_code=404, detail="Channel not found")
         
    db.query(WalkieChannelCabangs).filter(WalkieChannelCabangs.walkie_channel_id == id).delete()
    db.delete(channel)
    db.commit()
    
    return {"status": "success", "message": "Channel deleted successfully"}

# Helper endpoints for frontend dropdowns
@router.get("/options/cabang", response_model=List[CabangDTO])
async def get_cabang_options(db: Session = Depends(get_db)):
    return db.query(Cabang).order_by(Cabang.nama_cabang).all()

@router.get("/options/departemen", response_model=List[DepartemenDTO])
async def get_departemen_options(db: Session = Depends(get_db)):
    return db.query(Departemen).order_by(Departemen.kode_dept).all()
