from fastapi import APIRouter, Depends, Query, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models.models import WalkieChannels, WalkieChannelCabangs, Karyawan, Users, WalkieChannelCabangs
from app.routers.auth_legacy import get_current_user_data, CurrentUser, SECRET_KEY, ALGORITHM
from typing import List, Optional, Dict, Any
from jose import jwt

# Router for Android App
router = APIRouter(
    prefix="/api/android/walkie",
    tags=["Walkie Talkie Legacy (Android)"],
    responses={404: {"description": "Not found"}},
)

# Router for Node.js Server
router_node = APIRouter(
    prefix="/api/walkie",
    tags=["Walkie Talkie Node Backend"],
    responses={404: {"description": "Not found"}},
)

# --- HELPER LOGIC ---

def get_allowed_channels_query(db: Session, nik: str):
    # 1. Get Karyawan Data (Cabang & Dept)
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if not karyawan:
        return []

    kode_cabang = karyawan.kode_cabang
    kode_dept = karyawan.kode_dept
    # print(f"DEBUG: User {nik} Cabang={kode_cabang} Dept={kode_dept}", flush=True)

    # 2. Get All Active Channels
    channels = db.query(WalkieChannels).filter(WalkieChannels.active == 1).all()
    
    allowed = []
    for c in channels:
        # Check Department Membership (if defined)
        if c.dept_members:
            depts = [d.strip() for d in c.dept_members.split(',')]
            if kode_dept not in depts:
                continue # Skip if not in allowed dept
        
        # Check Cabang Membership (via relation)
        # Assuming rule_type='cabang_group' implies checking WalkieChannelCabangs
        # We check relation if it exists
        channel_cabangs = db.query(WalkieChannelCabangs).filter(WalkieChannelCabangs.walkie_channel_id == c.id).all()
        allowed_cabangs = [cc.kode_cabang for cc in channel_cabangs]
        
        # LOGIC: If channel has specific cabangs assigned, you MUST be in one of them.
        # If channel has NO cabangs assigned, is it open for all? Or closed? 
        # Usually checking 'allowed_cabangs' existence implies restriction.
        if allowed_cabangs and kode_cabang not in allowed_cabangs:
            continue # Skip if not in allowed cabang
            
        allowed.append(c)
        
    # Sort: Priority desc, Name asc
    allowed.sort(key=lambda x: (x.priority, x.name)) 
    
    return sorted(allowed, key=lambda x: x.priority, reverse=True)

# --- ANDROID ENDPOINT ---

@router.get("/channels", response_model=dict)
def get_android_channels(token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """
    Get list of active walkie talkie channels for Android app.
    Attempts to filter if token provided, otherwise returns all (legacy behavior).
    """
    user_nik = None
    if token:
        try:
             # Try decode to get user
             payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
             user_id = payload.get("sub")
             pivot = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user_id}).fetchone()
             if pivot:
                 user_nik = pivot[0]
        except:
            pass

    if user_nik:
         channels = get_allowed_channels_query(db, user_nik)
    else:
         # Fallback: all active channels
         channels = db.query(WalkieChannels).filter(WalkieChannels.active == 1).order_by(WalkieChannels.priority.desc(), WalkieChannels.code.asc()).all()
    
    data = []
    for c in channels:
        data.append({
            "id": c.id,
            "code": c.code,
            "name": c.name,
            "active": c.active,
            "auto_join": c.auto_join,
            "is_default": 1 if c.auto_join == 1 else 0 
        })
        
    return {
        "status": True,
        "message": "Success",
        "channels": data
    }


# --- NODE.JS ENDPOINTS ---

@router_node.get("/rooms", response_model=dict)
def get_node_rooms(current_user: CurrentUser = Depends(get_current_user_data), db: Session = Depends(get_db)):
    if not current_user.nik:
        return {"rooms": {}}
        
    channels = get_allowed_channels_query(db, current_user.nik)
    
    # Format: {"ROOM_CODE": [{"nik": "current_user_nik"}]} ?? 
    # Wait, Node expects: room -> [members].
    # But usually this endpoint just returns list of rooms allowed for the USER? 
    # Let's check server.cjs usage: resolveMemberRoom calls getRooms(token).
    # Then iterates keys (roomCodes).
    # So we just need to return keys. 
    # The output format expected by server.cjs: { "rooms": { "CODE": [] } } ?
    # server.cjs: const members = Array.isArray(roomsData[roomCode]) ...
    
    # It seems logic in server.cjs was: "Get all rooms and their members" (Admin view?)
    # BUT here we are checking permissions.
    # If we return { "ROOM_CODE": [] }, server.cjs uses it to check if user 'could' be in it?
    
    # Actually server.cjs:
    # 1. getRooms(token) -> returns ALL rooms?
    # 2. Iterates rooms to find if user is IN it?
    # resolveMemberRoom checks if user.nik is in the member list of the room.
    
    # But for "Allowed" check, we use /room/validate.
    
    # Let's return local format: { "rooms": { "CODE": [] } }
    # Or maybe we populate it with "allowed" flag?
    
    rooms_data = {}
    for c in channels:
        rooms_data[c.code] = [] # Empty list of members for now
        
    return {"rooms": rooms_data}

@router_node.get("/room/validate", response_model=dict)
def validate_node_room(token: str = Query(...), room: str = Query(...), db: Session = Depends(get_db)):
    # Manually decode token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        pivot = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user_id}).fetchone()
        nik = pivot[0] if pivot else None
        
        if not nik:
             return {"status": False, "allowed": False, "message": "No NIK found"}
             
        # Check permissions
        channels = get_allowed_channels_query(db, nik)
        allowed = any(c.code == room for c in channels)
        
        return {
            "status": True,
            "allowed": allowed,
            "room": room 
        }
        
    except Exception as e:
         return {"status": False, "allowed": False, "message": str(e)}

@router_node.get("/default", response_model=dict)
def get_node_default_channel(current_user: CurrentUser = Depends(get_current_user_data), db: Session = Depends(get_db)):
    if not current_user.nik:
         return {"default_channel": None}
         
    channels = get_allowed_channels_query(db, current_user.nik)
    
    # Find auto_join=1, sort by priority
    defaults = [c for c in channels if c.auto_join == 1]
    # channels are already sorted by priority desc
    
    default_code = defaults[0].code if defaults else None
    if not default_code and channels:
        default_code = channels[0].code # Fallback to first allowed
        
    return {
        "default_channel": { "code": default_code }
    }

@router_node.get("/channels", response_model=dict)
def get_node_channels(current_user: CurrentUser = Depends(get_current_user_data), db: Session = Depends(get_db)):
    if not current_user.nik:
         return {"channels": []}
         
    channels = get_allowed_channels_query(db, current_user.nik)
    data = [{"code": c.code, "name": c.name} for c in channels]
    
    return {"channels": data}
