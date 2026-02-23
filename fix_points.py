import os
import re
from datetime import datetime, date
from app.database import SessionLocal
from app.models.models import PatrolPoints, PatrolSessions
from sqlalchemy import delete

db = SessionLocal()

base_dir = '/var/www/appPatrol/storage/app/public/uploads/patroli/1803101204970002-20260223-patrol'
files = os.listdir(base_dir)
point_files = [f for f in files if 'patrol_point_' in f]

# get all 4 sessions we just restored today
# id: 8308, 8312, 8343, 8359
sessions = db.query(PatrolSessions).filter(PatrolSessions.id.in_([8308, 8312, 8343, 8359])).all()

# Delete existing incorrectly mapped points
db.query(PatrolPoints).filter(PatrolPoints.patrol_session_id.in_([8308, 8312, 8343, 8359])).delete(synchronize_session=False)

for pf in point_files:
    m = re.match(r'.*-patrol-(\d{2})(\d{2})(\d{2})-patrol_point_(\d+)_(\d+)', pf)
    if m:
        hr, mn, sc = int(m.group(1)), int(m.group(2)), int(m.group(3))
        master_id = int(m.group(4))
        
        # We need to map it based on the closest jam_patrol time instead of created_at
        pt_sec = hr*3600 + mn*60 + sc
        
        closest_session = None
        min_diff = None
        for s in sessions:
            s_time = getattr(s, 'jam_patrol', None)
            if s_time:
                s_sec = s_time.hour*3600 + s_time.minute*60 + s_time.second
                diff = abs(s_sec - pt_sec)
                if min_diff is None or diff < min_diff:
                    min_diff = diff
                    closest_session = s
        
        if closest_session:
            pt_time_obj = datetime(2026, 2, 23, hr, mn, sc)
            new_p = PatrolPoints(
                patrol_session_id=closest_session.id,
                patrol_point_master_id=master_id,
                foto=pf,
                lokasi='-4.8397961,104.8795094',
                jam=pt_time_obj.time(),
                created_at=pt_time_obj,
                updated_at=pt_time_obj
            )
            db.add(new_p)

db.commit()
db.close()
print("REASSIGNED POINTS BASED ON LOCAL TIME")
