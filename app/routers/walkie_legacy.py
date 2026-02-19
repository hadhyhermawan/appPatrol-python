from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import WalkieChannels
from typing import List, Optional

router = APIRouter(
    prefix="/api/android/walkie",
    tags=["Walkie Talkie Legacy"],
    responses={404: {"description": "Not found"}},
)

@router.get("/channels", response_model=dict)
def get_android_channels(token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Get list of active walkie talkie channels for Android app.
    This replaces the legacy Laravel endpoint /api/android/walkie/channels
    """
    # Simply return all active channels
    channels = db.query(WalkieChannels).filter(WalkieChannels.active == 1).order_by(WalkieChannels.priority.desc(), WalkieChannels.code.asc()).all()
    
    data = []
    for c in channels:
        data.append({
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "active": c.active,
            "auto_join": c.auto_join,
            "is_default": 1 if c.auto_join == 1 else 0 # Simple logic mapping
        })
        
    return {
        "status": True,
        "message": "Success",
        "channels": data
    }
