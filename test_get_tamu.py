from app.database import SessionLocal
from app.models.models import Tamu
db = SessionLocal()
last_tamu = db.query(Tamu).order_by(Tamu.id_tamu.desc()).first()
print(f"ID: {last_tamu.id_tamu}")
print(f"JAM MASUK: {last_tamu.jam_masuk}")
print(f"JAM MASUK TYPE: {type(last_tamu.jam_masuk)}")
