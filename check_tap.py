from app.database import SessionLocal
from app.models.models import Violation
db = SessionLocal()
taps = db.query(Violation).filter(Violation.violation_type == 'NO_CHECKOUT').all()
print("NO_CHECKOUT count:", len(taps))
other_taps = db.query(Violation).filter(Violation.keterangan.like('%Tidak Absen Pulang%') | Violation.keterangan.like('%Tidak melakukan checkout%')).all()
print("Other TAP count:", len(other_taps))
if other_taps:
    for t in other_taps[:5]:
        print(t.id, t.violation_type, t.keterangan)
