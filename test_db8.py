import sys
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
results = db.execute(text("""
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
        WHERE 1=1 ORDER BY ua.agreed_at DESC
""")).fetchall()
res = [dict(row._mapping) for row in results]
print("RESULT IS LIST:", isinstance(res, list))
print("DATA:", res)
db.close()
