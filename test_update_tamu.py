from app.database import SessionLocal
from app.models.models import Tamu
import requests

db = SessionLocal()
last_tamu = db.query(Tamu).order_by(Tamu.id_tamu.desc()).first()
print(f"Before update DB: {last_tamu.jam_masuk}")

# Simulate NextJS PUT /api/security/tamu/{id_tamu}
url = f"http://localhost:8000/api/security/tamu/{last_tamu.id_tamu}"
payload = {
    "nama": last_tamu.nama,
    "jam_masuk": "2026-02-21 15:30:00"
}
# wait, you need authentication for /api/security/?
# Let me just check how Pydantic parses "2026-02-21 15:30:00" when it goes into Optional[datetime]
