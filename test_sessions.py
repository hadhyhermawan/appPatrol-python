import asyncio
from app.database import SessionLocal
from app.models.models import PatrolSessions
from datetime import date
db = SessionLocal()

sessions = db.query(PatrolSessions).order_by(PatrolSessions.id.desc()).limit(15).all()
for s in sessions:
    print(f"ID: {s.id}, NIK: {s.nik}, Tanggal: {s.tanggal}, created_at: {s.created_at}")

