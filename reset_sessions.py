import sys
import datetime
import traceback
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from sqlalchemy import text

def reset_all_sessions():
    db = SessionLocal()
    try:
        # Get users with roles to exclude: 1, 2, 5, 6
        # 1: super admin, 2: admin departemen, 5: unit pelaksana pelayanan pelanggan, 6: unit layanan pelanggan
        query_excluded = text("SELECT DISTINCT model_id FROM model_has_roles WHERE role_id IN (1, 2, 5, 6)")
        excluded_rows = db.execute(query_excluded).fetchall()
        excluded_user_ids = [row[0] for row in excluded_rows]

        print(f"Total Admins to EXCLUDE from session reset: {len(excluded_user_ids)}")
        print(f"Excluded User IDs: {excluded_user_ids}")

        if excluded_user_ids:
            placeholders = ','.join([str(_id) for _id in excluded_user_ids])
            query_targets = text(f"SELECT id_user, nik FROM users_karyawan WHERE id_user NOT IN ({placeholders})")
        else:
            query_targets = text("SELECT id_user, nik FROM users_karyawan")

        targets = db.execute(query_targets).fetchall()
        
        target_user_ids = [row[0] for row in targets if row[0] is not None]
        target_niks = [row[1] for row in targets if row[1] is not None]

        print(f"Total Users/Karyawans to RESET session: {len(target_user_ids)}")

        # 1. Update `users` table: updated_at = NOW()
        if target_user_ids:
            chunk_size = 500
            for i in range(0, len(target_user_ids), chunk_size):
                chunk_ids = target_user_ids[i:i + chunk_size]
                ids_str = ','.join([str(_id) for _id in chunk_ids])
                update_users = text(f"UPDATE users SET updated_at = NOW() WHERE id IN ({ids_str})")
                db.execute(update_users)

        # 2. Update `karyawan` table: lock_device_login = '0'
        if target_niks:
            chunk_size = 500
            for i in range(0, len(target_niks), chunk_size):
                chunk_niks = target_niks[i:i + chunk_size]
                niks_str = ','.join([f"'{nik}'" for nik in chunk_niks])
                update_karyawans = text(f"UPDATE karyawan SET lock_device_login = '0' WHERE nik IN ({niks_str})")
                db.execute(update_karyawans)

        db.commit()
        print("Successfully reset sessions for all specified karyawans!")

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        print(f"Failed to reset sessions: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reset_all_sessions()
