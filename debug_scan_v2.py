
import sys
import traceback
from datetime import date
from app.database import SessionLocal
from app.routers.violations import scan_violations

# Setup DB
db = SessionLocal()

def log(msg):
    print(f"[DEBUG] {msg}")

try:
    log("Starting debug scan (calling actual function)...")
    results = scan_violations(date_scan=date.today(), db=db)
    log(f"Scan completed. Results count: {len(results)}")
    
    import json
    # Try serialization
    log("Attempting serialization...")
    json.dumps(results, default=str)
    log("Serialization successful.")
    
    for r in results:
        print(r)

except Exception as e:
    log(f"CRITICAL ERROR: {e}")
    traceback.print_exc()
finally:
    db.close()
