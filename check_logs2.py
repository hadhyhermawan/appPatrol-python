from app.database import SessionLocal
from app.models.models import LoginLogs
from sqlalchemy import text
db = SessionLocal()
# Check some recent login logs
logs = db.query(LoginLogs).order_by(LoginLogs.id.desc()).limit(20).all()
for l in logs:
    print(f"ID: {l.id}, User: {l.user_id}, Device: {l.device}, Android Ver: {l.android_version}")
