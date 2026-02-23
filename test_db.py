import sys
import os
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    sql = """
        SELECT ua.id, ua.terms_version, ua.privacy_version, ua.device_info, ua.agreed_at,
               u.name as user_name, u.email as user_email, u.username as user_nik,
               d.nama_dept as department_name, c.nama_cabang as branch_name, j.nama_jabatan as position_name
        FROM user_agreements ua
        JOIN users u ON ua.user_id = u.id
        LEFT JOIN users_karyawan uk ON u.id = uk.id_user
        LEFT JOIN karyawan k ON (uk.nik = k.nik OR u.username = k.nik)
        LEFT JOIN departemen d ON k.kode_dept = d.kode_dept
        LEFT JOIN cabang c ON k.kode_cabang = c.kode_cabang
        LEFT JOIN jabatan j ON k.kode_jabatan = j.kode_jabatan
        WHERE 1=1 ORDER BY ua.agreed_at DESC LIMIT 5
    """
    results = db.execute(text(sql)).fetchall()
    
    for row in results:
        print(f"ID: {row.id}")
        print(f"Name: {repr(row.user_name)}")
        print(f"Nik: {repr(row.user_nik)}")
        print(f"Terms: {repr(row.terms_version)}")
        print(f"Date: {repr(row.agreed_at)}")
        print("---")
except Exception as e:
    print(f"Error: {e}")
finally:
    db.close()
