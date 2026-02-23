import sys
import pytz
from datetime import datetime
sys.path.append('/var/www/appPatrol-python')

from app.database import SessionLocal
from app.models.models import Presensi

db = SessionLocal()
now = datetime.now(pytz.timezone('Asia/Jakarta'))
today = now.date()
nik = '1801032008930004'

presensiku = db.query(Presensi).filter(Presensi.nik == nik, Presensi.tanggal == today).all()
for p in presensiku:
    print("Deleting Presensi ID:", p.id)
    db.delete(p)

db.commit()
print("Berhasil menghapus presensi.")

db.close()
