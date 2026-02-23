from app.database import SessionLocal
from app.models.models import SecurityReports, LoginLogs
from sqlalchemy import or_

db = SessionLocal()
empty_ip_reps = db.query(SecurityReports).filter(
    (SecurityReports.ip_address == None) | (SecurityReports.ip_address == '')
).all()

count = 0
for rep in empty_ip_reps:
    ll = db.query(LoginLogs).filter(
        LoginLogs.user_id == rep.user_id,
        LoginLogs.ip != None,
        LoginLogs.ip != ''
    ).order_by(LoginLogs.id.desc()).first()
    
    if ll:
        rep.ip_address = ll.ip
        count += 1
    else:
        # fallback if no login logs
        rep.ip_address = "Unknown"
        count += 1

db.commit()
print(f"Backfilled {count} empty IPs in SecurityReports!")
