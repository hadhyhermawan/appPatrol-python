import sys
from fastapi.testclient import TestClient
from app.main import app_fastapi as app
from app.database import SessionLocal
from app.models.models import Users, Userkaryawan, Violation
from app.auth.security import create_access_token

def test_api():
    db = SessionLocal()
    try:
        # Find a user who has violations
        violation = db.query(Violation).first()
        if not violation:
            print("No violations found in DB.")
            return

        user_karyawan = db.query(Userkaryawan).filter(Userkaryawan.nik == violation.nik).first()
        if not user_karyawan:
            print(f"No user linked to NIK {violation.nik}")
            return
        
        user = db.query(Users).filter(Users.id == user_karyawan.id_user).first()
        if not user:
            print("No user found")
            return

        print(f"Testing with User: {user.username}, NIK: {violation.nik}")

        # Create token
        access_token = create_access_token(data={"sub": str(user.id), "nik": user_karyawan.nik})
        print(f"Token created: {access_token[:20]}...")

        client = TestClient(app)
        response = client.get(
            "/api/android/violations/my",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        print(f"Status Code: {response.status_code}")
        print("Response JSON:")
        import json
        print(json.dumps(response.json(), indent=2))
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_api()
