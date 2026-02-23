from app.database import SessionLocal
from app.models.models import PatrolSessions
db = SessionLocal()

updates = {
    8308: '1803101204970002-20260223-160118000-absen-patrol.png',
    8343: '1803101204970002-20260223-absenpatrol-200019-patrol_compressed6170445676168381687.jpg',
    8359: '1803101204970002-20260223-absenpatrol-220014-patrol_compressed5870712275374671699.jpg'
}

for sid, fname in updates.items():
    s = db.query(PatrolSessions).filter(PatrolSessions.id == sid).first()
    if s:
        s.foto_absen = fname
        
db.commit()
print('fixed foto absen')
