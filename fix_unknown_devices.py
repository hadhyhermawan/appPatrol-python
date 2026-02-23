from app.database import SessionLocal
from app.models.models import SecurityReports, LoginLogs, KaryawanDevices, Users
from sqlalchemy import desc

db = SessionLocal()
reports = db.query(SecurityReports).filter(SecurityReports.device_model == 'Unknown').all()

updated = 0
for rep in reports:
    # 1. Try to find from LoginLogs based on user_id
    if rep.user_id:
        ll = db.query(LoginLogs).filter(
            LoginLogs.user_id == rep.user_id,
            LoginLogs.android_version != None,
            LoginLogs.device != None,
            LoginLogs.device != 'Unknown'
        ).order_by(desc(LoginLogs.id)).first()
        
        if ll:
            rep.device_model = ll.device
            updated += 1
            continue

    # 2. Try to find from KaryawanDevices based on nik
    if rep.nik:
        kd = db.query(KaryawanDevices).filter(
            KaryawanDevices.nik == rep.nik
        ).order_by(desc(KaryawanDevices.id)).first()
        
        # fallback to users table id?
        # just getting device_id doesn't give us device_model directly, let's see if KaryawanDevices has device_type?
        # KaryawanDevices only has device_id (usually a hash like c82... not a readable model string).
        
        # If we couldn't find it from LoginLogs user_id, let's try finding the user_id by nik
        if not rep.user_id:
            user = db.query(Users).filter(Users.username == rep.nik).first()
            if user:
                rep.user_id = user.id
                ll = db.query(LoginLogs).filter(
                    LoginLogs.user_id == user.id,
                    LoginLogs.android_version != None,
                    LoginLogs.device != None,
                    LoginLogs.device != 'Unknown'
                ).order_by(desc(LoginLogs.id)).first()
                if ll:
                    rep.device_model = ll.device
                    updated += 1
                    continue

db.commit()
print(f"Backfilled {updated} Unknown devices gracefully!")
