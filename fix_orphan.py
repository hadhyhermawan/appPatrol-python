from app.database import SessionLocal
from app.models.models import Karyawan, Violation
from sqlalchemy import text

db = SessionLocal()

orphan_q = text("""
   SELECT v.id
   FROM violations v
   LEFT JOIN karyawan k ON v.nik = k.nik
   WHERE k.nik IS NULL
""")
orphans = db.execute(orphan_q).fetchall()
print(f"Orphan ID in violations: {len(orphans)}")

if len(orphans) > 0:
    for o in orphans:
        print(f"Deleting ID {o[0]}")
        db.execute(text(f"DELETE FROM violations WHERE id={o[0]}"))
    db.commit()
    print("Orphans dihapus")

print("Checking query again")
from app.routers.violations import get_violations
try:
    results = get_violations(1, 10, None, None, None, "absent", db)
    print("YAY WORKS. Returns count:", len(results))
except Exception as e:
    import traceback
    traceback.print_exc()

