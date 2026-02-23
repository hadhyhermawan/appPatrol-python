import asyncio
from app.database import SessionLocal
from app.models.models import SecurityReports
import sys

db = SessionLocal()
reports = db.query(SecurityReports).order_by(SecurityReports.id.desc()).limit(20).all()
for r in reports:
    print(f"ID: {r.id}, Type: {r.type}, Detail: {r.detail}, Device: {r.device_model}")

