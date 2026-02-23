from app.database import SessionLocal
from app.models.models import LoginLogs
db = SessionLocal()
logs = db.query(LoginLogs).order_by(LoginLogs.id.desc()).limit(10).all()
for l in logs:
    print(f"ID: {l.id}, User: {l.user_id}, Device: {l.device}")
