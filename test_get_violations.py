from app.database import SessionLocal
from app.routers.violations import get_violations
import traceback

db = SessionLocal()
try:
    print("Mulai panggil get_violations...")
    res = get_violations(1, 10, None, None, None, "absent", db)
    print("Selesai!", len(res))
except Exception as e:
    traceback.print_exc()
