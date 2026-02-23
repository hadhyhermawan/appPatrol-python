from app.database import SessionLocal
from app.models.models import PatrolSchedules

db = SessionLocal()
schedules = db.query(PatrolSchedules).all()
print(f"Total schedules: {len(schedules)}")
for s in schedules:
    print(s.id, s.name, repr(s.kode_jam_kerja), repr(s.kode_dept), repr(s.kode_cabang), s.is_active)
