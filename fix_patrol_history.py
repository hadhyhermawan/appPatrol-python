import re

with open("app/routers/patroli_legacy.py", "r") as f:
    text = f.read()

# Replace the incorrect created_at filter in _build_schedule_tasks_for_day
old_block = """        # Apakah sudah ada session dalam window ini dari grup?
        session_in_window = db.query(PatrolSessions).filter(
            PatrolSessions.nik.in_(group_niks),
            PatrolSessions.created_at >= start_dt,
            PatrolSessions.created_at <= end_dt
        ).first()"""

new_block = """        # Apakah sudah ada session dalam window ini dari grup?
        # Gunakan tanggal dan jam_patrol, MENGABAIKAN created_at yang bisa bermasalah zona waktu
        group_sessions = db.query(PatrolSessions).filter(
            PatrolSessions.nik.in_(group_niks),
            PatrolSessions.tanggal == target_date
        ).all()
        
        session_in_window = None
        for sess in group_sessions:
            if sess.jam_patrol:
                sess_date_base = sess.tanggal
                if is_lintashari and sess.jam_patrol < jam_kerja.jam_masuk:
                    sess_date_base = sess_date_base + timedelta(days=1)
                
                sess_dt = datetime.combine(sess_date_base, sess.jam_patrol)
                if start_dt <= sess_dt <= end_dt:
                    session_in_window = sess
                    break"""

if old_block in text:
    text = text.replace(old_block, new_block)
    with open("app/routers/patroli_legacy.py", "w") as f:
        f.write(text)
    print("Fixed!")
else:
    print("Block not found!")
