from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile, Request, Body, Query, Path
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text, distinct
from app.database import get_db
from app.models.models import Karyawan, WalkieRtcMessages, Users
from app.core.permissions import get_current_user
from app.core.fcm import send_chat_notification
from datetime import datetime
import shutil, os, secrets, asyncio
from typing import Optional, List, Dict, Any, Union

router = APIRouter(
    prefix="/api/android/chat", # Matches android retrofit Base URL + @POST("chat/send")
    tags=["Obrolan Legacy"],
    dependencies=[Depends(get_current_user)],
    responses={404: {"description": "Not found"}},
)

# Update UPLOAD_DIR to local static folder (Python-only)
UPLOAD_DIR = "/var/www/appPatrol-python/static/chat"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# URL untuk akses file via browser/app
BASE_STORAGE_URL = "https://frontend.k3guard.com/api-py/static"

def format_response(success: bool, message: str, data: Any = None):
    return {"status": success, "message": message, "data": data}

@router.get("/messages/{room}")
async def get_messages(room: str, db: Session = Depends(get_db)):
    try:
        # Fetch latest 50 messages
        msgs = db.query(WalkieRtcMessages)\
                 .filter(WalkieRtcMessages.room == room)\
                 .order_by(desc(WalkieRtcMessages.created_at))\
                 .limit(50)\
                 .all()
        
        # Reverse to show oldest first (chronological) 
        msgs.reverse()
        
        results = []
        for m in msgs:
            reply_sender_nama = None
            reply_message = None
            reply_attachment = None
            reply_attachment_type = None
            reply_to_str = None
            
            if m.reply_to and m.reply_to.isdigit():
                reply_to_str = str(m.reply_to)
                parent = db.query(WalkieRtcMessages).filter(WalkieRtcMessages.id == int(m.reply_to)).first()
                if parent:
                    reply_sender_nama = parent.sender_nama
                    reply_message = parent.message
                    if parent.attachment:
                        reply_attachment = parent.attachment if parent.attachment.startswith("http") else f"{BASE_STORAGE_URL}/{parent.attachment}"
                    reply_attachment_type = parent.attachment_type

            # Format current attachment
            attachment_url = None
            if m.attachment:
                 attachment_url = m.attachment if m.attachment.startswith("http") else f"{BASE_STORAGE_URL}/{m.attachment}"

            results.append({
                "id": m.id,
                "room": m.room,
                "sender_id": m.sender_id or "",
                "sender_nama": m.sender_nama,
                "role": m.role,
                "message": m.message,
                "created_at": m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else "",
                "reply_to": reply_to_str,
                "reply_sender_nama": reply_sender_nama,
                "reply_message": reply_message,
                "reply_attachment": reply_attachment,
                "reply_attachment_type": reply_attachment_type,
                "attachment": attachment_url,
                "attachment_type": m.attachment_type
            })
            
        return format_response(True, "Success", results)
    except Exception as e:
        return format_response(False, str(e), [])

@router.post("/send")
async def send_message(request: Request, db: Session = Depends(get_db)):
    try:
        content_type = request.headers.get("content-type", "")
        print(f"DEBUG SEND: content-type={content_type}")
        
        data = {}
        file = None
        
        if "application/json" in content_type:
            data = await request.json()
        elif "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            print(f"DEBUG SEND: form keys={form.keys()}")
            data = form
            file = form.get("attachment")
            if file:
                print(f"DEBUG SEND: file received. name={file.filename} content_type={file.content_type}")
            else:
                print("DEBUG SEND: simple form data, no file")
        
        # Extract fields
        room = data.get("room")
        # Android sends 'nik' OR 'sender_id'. Handle both.
        sender_id = data.get("sender_id") or data.get("nik")
        sender_nama = data.get("sender_nama")
        role = data.get("role")
        message = data.get("message")
        reply_to = data.get("reply_to")
        
        if not room or not sender_id:
             raise HTTPException(status_code=400, detail="Missing required fields (room, sender_id/nik)")

        if not message and not file:
             print("DEBUG SEND: Message and File empty -> Rejecting")
             raise HTTPException(status_code=400, detail="Pesan atau file tidak boleh kosong.")

        attachment_path = None
        attachment_type = None

        # Handle File Upload
        if file:
            filename = f"{int(datetime.now().timestamp())}_{secrets.token_hex(4)}_{file.filename}"
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            # Async read/write
            content = await file.read()
            with open(file_path, "wb") as buffer:
                buffer.write(content)
                
            # Path for frontend/API access
            attachment_path = f"chat/{filename}"
            
            if file.content_type.startswith("image/"):
                attachment_type = "image"
            elif file.content_type.startswith("video/"):
                attachment_type = "video"
            elif file.content_type.startswith("application/pdf"):
                 attachment_type = "pdf"
            else:
                attachment_type = "file"

        # Create Message
        # Fix: Android sometimes sends NIK as sender_nama. Force lookup actual name.
        karyawan = db.query(Karyawan).filter(Karyawan.nik == sender_id).first()
        actual_sender_nama = karyawan.nama_karyawan if karyawan else (sender_nama or sender_id)

        new_msg = WalkieRtcMessages(
            room=room,
            sender_id=sender_id,
            sender_nama=actual_sender_nama,
            role=role or "user",
            message=message or "",
            reply_to=str(reply_to) if reply_to else None,
            attachment=attachment_path,
            attachment_type=attachment_type,
            created_at=datetime.now()
        )
        
        db.add(new_msg)
        db.commit()
        db.refresh(new_msg)

        # 🔔 KIRIM PUSH NOTIFICATION ke peserta lain di room
        try:
            # Ambil daftar NIK peserta lain yang pernah chat di room ini
            other_niks_result = db.query(WalkieRtcMessages.sender_id).filter(
                WalkieRtcMessages.room == room,
                WalkieRtcMessages.sender_id != sender_id,
                WalkieRtcMessages.sender_id.isnot(None)
            ).distinct().all()

            other_niks = [r[0] for r in other_niks_result if r[0]]

            if other_niks:
                preview = message or ("📎 Mengirim foto" if attachment_type == "image" else "📎 Mengirim video" if attachment_type == "video" else "📎 Mengirim file")
                # Ambil nama asli pengirim dari karyawan jika ada
                karyawan = db.query(Karyawan).filter(Karyawan.nik == sender_id).first()
                nama_pengirim = karyawan.nama_karyawan if karyawan else (sender_nama or sender_id)

                # Kirim notif di background (non-blocking)
                loop = asyncio.get_event_loop()
                loop.run_in_executor(
                    None,
                    lambda: send_chat_notification(other_niks, nama_pengirim, preview, room, db)
                )
                print(f"[FCM CHAT] Memulai push notif ke {len(other_niks)} NIK | room={room}")
            else:
                print(f"[FCM CHAT] Tidak ada NIK lain di room {room}")
        except Exception as fcm_err:
            # Jangan gagalkan request hanya karena notifikasi gagal
            print(f"[FCM CHAT] Error push notif (non-fatal): {fcm_err}")

        return format_response(True, "Pesan terkirim", {"id": new_msg.id})

    except Exception as e:
        print(f"Error sending message: {e}")
        return format_response(False, str(e), None)
