from app.database import SessionLocal
from app.routers.violations import scan_violations
from datetime import date, timedelta
db = SessionLocal()
yesterday = date.today() - timedelta(days=1)
res = scan_violations(yesterday, db)
print(f"Scanned for {yesterday}: {len(res)} violations found.")
for r in res:
    if r['violation_code'] == 'NO_CHECKOUT':
        print(r)
