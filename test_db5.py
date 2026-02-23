import sys
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
results = db.execute(text("""
    SELECT count(*)
    FROM user_agreements ua
    JOIN users u ON ua.user_id = u.id
    LEFT JOIN users_karyawan uk ON u.id = uk.id_user
    LEFT JOIN karyawan k ON (uk.nik = k.nik OR u.username = k.nik)
""")).scalar()
print("TOTAL WITH JOIN:", results)
db.close()
