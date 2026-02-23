import sys
from app.database import SessionLocal
from app.models.models import Violation
import json

def check_db():
    db = SessionLocal()
    try:
        violations = db.query(Violation).limit(10).all()
        result = []
        for v in violations:
            result.append({
                "id": v.id,
                "nik": v.nik,
                "jenis_pelanggaran": v.jenis_pelanggaran,
                "tanggal_pelanggaran": str(v.tanggal_pelanggaran),
                "keterangan": v.keterangan,
                "is_read": getattr(v, "is_read", None)
            })
        print(f"Total violations found: {db.query(Violation).count()}")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_db()
