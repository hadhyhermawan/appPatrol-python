from fastapi.testclient import TestClient
from app.main import app
import sys

# Disable exception catching so we get the full stack trace
client = TestClient(app, raise_server_exceptions=True)

try:
    response = client.get("/api/laporan/rekap-presensi?start_date=2026-02-01&end_date=2026-02-27&search=WIRAWAN")
    print("STATUS CODE:", response.status_code)
    print("RESPONSE TEXT:", response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
