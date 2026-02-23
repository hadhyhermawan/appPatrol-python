from app.database import SessionLocal
from app.models.models import Violation
from sqlalchemy import text

db = SessionLocal()
print("Cleaning duplicated violations from earlier insert...")

# Find duplicates
q = text("""
    SELECT nik, tanggal_pelanggaran, violation_type, count(*) 
    FROM violations 
    GROUP BY nik, tanggal_pelanggaran, violation_type 
    HAVING count(*) > 1
""")
dupes = db.execute(q).fetchall()
print(f"Number of dupes groups: {len(dupes)}")

for nik, tgl, tipe, cnt in dupes:
    print(f"Repairing {nik} {tgl} {tipe}")
    # get all ids
    q_ids = text(f"SELECT id FROM violations WHERE nik='{nik}' AND tanggal_pelanggaran='{tgl}' AND violation_type='{tipe}' ORDER BY id ASC")
    ids = [row[0] for row in db.execute(q_ids).fetchall()]
    # Keep the first, delete the rest
    if len(ids) > 1:
        ids_to_del = ids[1:]
        id_str = ",".join([str(i) for i in ids_to_del])
        print("will del: ", id_str)
        db.execute(text(f"DELETE FROM violations WHERE id IN ({id_str})"))

db.commit()
print("Selesai")

from app.routers.violations import get_violations
print("Test get again:")
try:
    results = get_violations(1, 10, None, None, None, "absent", db)
    print("YAY WORKS. Returns count:", len(results))
except Exception as e:
    import traceback
    traceback.print_exc()

