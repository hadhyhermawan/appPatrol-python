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
    LEFT JOIN departemen d ON k.kode_dept = d.kode_dept
    LEFT JOIN cabang c ON k.kode_cabang = c.kode_cabang
    LEFT JOIN jabatan j ON k.kode_jabatan = j.kode_jabatan
""")).scalar()
print("TOTAL FULL JOIN:", results)
db.close()
