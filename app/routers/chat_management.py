from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_, and_, distinct, select, text
from app.database import get_db
from app.models.models import Karyawan, WalkieRtcMessages
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, date
import shutil
import os
import secrets

router = APIRouter(
    prefix="/api/chat-management",
    tags=["Chat Management"],
    responses={404: {"description": "Not found"}},
)

UPLOAD_DIR = "/var/www/appPatrol/storage/app/public/chat"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class ThreadSummaryDTO(BaseModel):
    room: str
    total_messages: int
    total_participants: int
    last_message_id: int
    last_sender_id: Optional[str]
    last_sender_name: Optional[str]
    last_message_text: Optional[str]
    last_message_at: Optional[datetime]

class ChatMessageDTO(BaseModel):
    id: int
    room: str
    sender_id: Optional[str]
    sender_nama: str
    role: str
    message: str
    created_at: Optional[datetime]
    reply_to: Optional[str]
    attachment: Optional[str]
    attachment_type: Optional[str]
    reply_sender_nama: Optional[str] = None
    reply_message: Optional[str] = None

class CreateMessageDTO(BaseModel):
    room: str
    message: Optional[str] = None
    sender_id: str  # Assuming sender is passed or extracted from token
    sender_nama: str
    role: str

@router.get("", response_model=dict)
async def get_chat_threads(
    room: Optional[str] = None,
    sender: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(WalkieRtcMessages)

    if room:
        query = query.filter(WalkieRtcMessages.room.ilike(f"%{room}%"))
    if sender:
        query = query.filter(or_(
            WalkieRtcMessages.sender_id.ilike(f"%{sender}%"),
            WalkieRtcMessages.sender_nama.ilike(f"%{sender}%")
        ))
    if q:
         query = query.filter(WalkieRtcMessages.message.ilike(f"%{q}%"))
    if date_from:
        query = query.filter(func.date(WalkieRtcMessages.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(WalkieRtcMessages.created_at) <= date_to)

    # Summary Stats
    total_messages = query.count()
    total_threads = query.with_entities(WalkieRtcMessages.room).distinct().count()
    total_senders = query.with_entities(WalkieRtcMessages.sender_id).distinct().count()

    # Get Latest Message per Room
    subquery = query.with_entities(
        WalkieRtcMessages.room,
        func.max(WalkieRtcMessages.id).label('last_id')
    ).group_by(WalkieRtcMessages.room).subquery()

    latest_messages = db.query(WalkieRtcMessages).join(
        subquery, WalkieRtcMessages.id == subquery.c.last_id
    )

    # Build response logic manually since Group By in SQLAlchemy can be tricky with full object return
    # We want: room, count messages, count participants, last message details
    
    # Let's paginate the ROOMS (threads) not messages
    rooms_query = query.with_entities(WalkieRtcMessages.room).distinct()
    total_rooms = rooms_query.count()
    
    # Apply pagination on rooms
    offset = (page - 1) * limit
    rooms = rooms_query.limit(limit).offset(offset).all()
    room_names = [r[0] for r in rooms]
    
    threads_data = []
    
    for r_name in room_names:
        # Get stats for this room based on filters
        room_msgs = query.filter(WalkieRtcMessages.room == r_name)
        msg_count = room_msgs.count()
        part_count = room_msgs.with_entities(WalkieRtcMessages.sender_id).distinct().count()
        
        # Get last message
        last_msg = room_msgs.order_by(desc(WalkieRtcMessages.created_at)).first()
        
        threads_data.append({
            "room": r_name,
            "total_messages": msg_count,
            "total_participants": part_count,
            "last_message_id": last_msg.id if last_msg else 0,
            "last_sender_id": last_msg.sender_id if last_msg else None, 
            "last_sender_name": last_msg.sender_nama if last_msg else None,
            "last_message_text": last_msg.message if last_msg else None,
            "last_message_at": last_msg.created_at if last_msg else None
        })

    # Sort threads by last message date desc (in Python for simplicity, though suboptimal for huge datasets)
    threads_data.sort(key=lambda x: x['last_message_at'] or datetime.min, reverse=True)

    return {
        "data": threads_data,
        "summary": {
            "total_messages": total_messages,
            "total_threads": total_threads,
            "total_senders": total_senders
        },
        "meta": {
            "page": page,
            "limit": limit,
            "total": total_rooms
        }
    }

@router.get("/thread/{room}", response_model=dict)
async def get_thread_messages(
    room: str,
    sender: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    # Verify room exists (or decrypt if we were using encrypted rooms, but for now assuming plain room name or handling frontend logic)
    # The Laravel controller decrypts, implying the URL param is encrypted. 
    # For this implementation, we will assume the frontend passes the raw room name or handles encryption.
    # If encryption is strictly required on backend, we need the APP_KEY. Let's assume raw for now to match typical REST patterns unless specified.
    
    query = db.query(WalkieRtcMessages).filter(WalkieRtcMessages.room == room)

    if sender:
         query = query.filter(or_(
            WalkieRtcMessages.sender_id.ilike(f"%{sender}%"),
            WalkieRtcMessages.sender_nama.ilike(f"%{sender}%")
        ))
    if q:
         query = query.filter(WalkieRtcMessages.message.ilike(f"%{q}%"))
    if date_from:
        query = query.filter(func.date(WalkieRtcMessages.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(WalkieRtcMessages.created_at) <= date_to)

    # Pagination
    total_messages = query.count()
    offset = (page - 1) * limit
    
    # Aliases for self-join (replies)
    # Since SQLAlchemy models are mapped, we can do a left outer join on the same table
    # But for simplicity and avoiding complex ORM self-referential setups without explicit relationships defined in model, 
    # we can fetch messages and manually resolve replies or use a simpler query.
    # The Laravel code joins with Karyawan and Self.
    
    messages = query.order_by(desc(WalkieRtcMessages.created_at)).limit(limit).offset(offset).all()
    
    result = []
    for m in messages:
        reply_sender = None
        reply_msg = None
        if m.reply_to:
            # Fetch reply content (N+1 issue here, optimize if needed later)
            # Since reply_to is a string in model but ID in Laravel logic? 
            # Model says: reply_to: Mapped[Optional[str]] = mapped_column(String(255))
            # Laravel controller: leftJoin('walkie_rtc_messages as r', 'm.reply_to', '=', 'r.id')
            # So reply_to likely holds the ID as string.
            if m.reply_to and m.reply_to.isdigit():
                 parent = db.query(WalkieRtcMessages).filter(WalkieRtcMessages.id == int(m.reply_to)).first()
                 if parent:
                     reply_sender = parent.sender_nama
                     reply_msg = parent.message
        
        # Resolve sender name from Karyawan if possible (Laravel does COALESCE(k.nama_karyawan, m.sender_nama))
        sender_name = m.sender_nama
        if m.sender_id:
             karyawan = db.query(Karyawan).filter(Karyawan.nik == m.sender_id).first()
             if karyawan:
                 sender_name = karyawan.nama_karyawan

        result.append({
            "id": m.id,
            "room": m.room,
            "sender_id": m.sender_id,
            "sender_nama": sender_name,
            "role": m.role,
            "message": m.message,
            "created_at": m.created_at,
            "reply_to": m.reply_to,
            "attachment": m.attachment,
            "attachment_type": m.attachment_type,
            "reply_sender_nama": reply_sender,
            "reply_message": reply_msg
        })

    # Participants Stats
    participants = db.query(
        WalkieRtcMessages.sender_id, 
        WalkieRtcMessages.sender_nama, 
        func.count(WalkieRtcMessages.id).label('count')
    ).filter(WalkieRtcMessages.room == room)\
    .group_by(WalkieRtcMessages.sender_id, WalkieRtcMessages.sender_nama)\
    .order_by(desc('count'))\
    .all()
    
    participants_list = [{"sender_id": p.sender_id, "sender_nama": p.sender_nama, "count": p.count} for p in participants]

    # Room Summary
    first_msg = db.query(func.min(WalkieRtcMessages.created_at)).filter(WalkieRtcMessages.room == room).scalar()
    last_msg = db.query(func.max(WalkieRtcMessages.created_at)).filter(WalkieRtcMessages.room == room).scalar()
    
    return {
        "data": result,
        "participants": participants_list,
        "summary": {
             "total_messages": total_messages,
             "total_participants": len(participants_list),
             "first_message_at": first_msg,
             "last_message_at": last_msg
        },
        "meta": {
            "page": page,
            "limit": limit,
            "total": total_messages
        }
    }

@router.post("/send")
async def send_message(
    room: str = Form(...),
    message: Optional[str] = Form(None),
    role: str = Form("admin"), 
    sender_id: str = Form(...), # Pass from frontend auth context
    sender_nama: str = Form(...),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    if not message and not file:
        raise HTTPException(status_code=400, detail="Pesan atau file tidak boleh kosong.")

    attachment_path = None
    attachment_type = None

    if file:
        # Generate safe filename
        filename = f"{int(datetime.now().timestamp())}_{secrets.token_hex(4)}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Determine type
        content_type = file.content_type
        if content_type.startswith("image/"):
            attachment_type = "image"
        else:
            attachment_type = "file"
            
        # Path relative to storage for public access (adjust based on static file serving config)
        # Assuming FastAPI serves /storage or similar
        attachment_path = f"chat/{filename}"

    new_msg = WalkieRtcMessages(
        room=room,
        sender_id=sender_id,
        sender_nama=sender_nama,
        role=role,
        message=message if message else "",
        attachment=attachment_path,
        attachment_type=attachment_type,
        created_at=datetime.now()
    )
    
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    
    return {"status": "success", "data": {"id": new_msg.id}}

@router.delete("/{id}")
async def delete_message(id: int, db: Session = Depends(get_db)):
    msg = db.query(WalkieRtcMessages).filter(WalkieRtcMessages.id == id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    # Handle replies (set null)
    # Assuming reply_to stores ID as string
    replies = db.query(WalkieRtcMessages).filter(WalkieRtcMessages.reply_to == str(id)).all()
    for r in replies:
        r.reply_to = None
    
    # Delete attachment if exists
    if msg.attachment:
        # Clean up file logic here if needed
        pass

    db.delete(msg)
    db.commit()
    return {"status": "success", "message": "Message deleted"}

@router.delete("/thread/{room}")
async def delete_thread(room: str, db: Session = Depends(get_db)):
    msgs = db.query(WalkieRtcMessages).filter(WalkieRtcMessages.room == room).all()
    if not msgs:
         raise HTTPException(status_code=404, detail="Thread not found")
         
    for msg in msgs:
        if msg.attachment:
            # detailed file cleanup logic
            pass
            
    db.query(WalkieRtcMessages).filter(WalkieRtcMessages.room == room).delete()
    db.commit()
    
    return {"status": "success", "message": "Thread deleted"}
