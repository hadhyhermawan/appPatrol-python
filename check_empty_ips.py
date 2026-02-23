from app.database import SessionLocal
from app.models.models import SecurityReports
from sqlalchemy import or_

db = SessionLocal()
reps = db.query(SecurityReports).filter(or_(SecurityReports.ip_address == None, SecurityReports.ip_address == '')).limit(20).all()
for r in reps:
    print(f'ID: {r.id}, User ID: {r.user_id}, Type: {r.type}, IP: {r.ip_address}, Created At: {r.created_at}')
