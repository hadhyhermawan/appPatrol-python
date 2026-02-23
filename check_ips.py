from app.database import SessionLocal
from app.models.models import SecurityReports, LoginLogs
db = SessionLocal()
empty_ip_reps = db.query(SecurityReports).filter(
    (SecurityReports.ip_address == None) | (SecurityReports.ip_address == '')
).all()

print(f"Total reports with empty IP: {len(empty_ip_reps)}")
for rep in empty_ip_reps[:5]:
    ll = db.query(LoginLogs).filter(LoginLogs.user_id == rep.user_id).order_by(LoginLogs.id.desc()).first()
    print(f"Rep ID: {rep.id}, Type: {rep.type}, LL IP: {ll.ip if ll else 'No LL'}")

