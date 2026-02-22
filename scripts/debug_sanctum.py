from app.database import SessionLocal
from app.models.models import PersonalAccessTokens
import hashlib

db = SessionLocal()

# Token from log
RAW_TOKEN = "4467|qLnJBstWJE4wvGR0XXv6xI2kzzhE6IENQQaCl9ZH3a8c5c2b"

print(f"Debug Sanctum Token: {RAW_TOKEN}")

if "|" not in RAW_TOKEN:
    print("Invalid format (no pipe)")
else:
    token_id, token_value = RAW_TOKEN.split("|", 1)
    print(f"ID: {token_id}")
    print(f"Value: {token_value}")
    
    # 1. Hashing
    hashed_value = hashlib.sha256(token_value.encode()).hexdigest()
    print(f"Computed Hash (SHA256): {hashed_value}")
    
    # 2. DB Check
    pat = db.query(PersonalAccessTokens).filter(PersonalAccessTokens.id == token_id).first()
    
    if not pat:
        print("Token NOT FOUND in DB")
    else:
        print(f"DB Token Hash: {pat.token}")
        
        if pat.token == hashed_value:
            print("Status: ✅ MATCH (VALID)")
        else:
            print("Status: ❌ MISMATCH (INVALID)")
            
db.close()
