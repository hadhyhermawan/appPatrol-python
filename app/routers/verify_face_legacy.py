from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from app.routers.auth_legacy import get_current_user_nik
from app.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/android/deteksiwajah",
    tags=["Face Verification (Legacy)"],
    responses={404: {"description": "Not found"}},
)

@router.post("/verify")
async def verify_face(
    image: UploadFile = File(...),
    nik: str = Form(...),
    db: Session = Depends(get_db)
):
    import httpx
    from sqlalchemy import text
    
    # URL Service Flask (Port 5000)
    FLASK_SERVICE_URL = "http://localhost:5000/api/deteksiwajah/verify"
    
    try:
        # Read file content
        file_content = await image.read()
        
        async with httpx.AsyncClient() as client:
            # Forward request to Flask service
            response = await client.post(
                FLASK_SERVICE_URL,
                data={"nik": nik},
                files={"image": (image.filename, file_content, image.content_type)},
                timeout=30.0 # DeepFace can be slow
            )
            
            # Check if service is down or error
            if response.status_code != 200:
                print(f"Flask Service Error: {response.text}")
                return {
                     "status": False,
                     "message": "Face Service Error/Timeout",
                     "detail": response.text
                }

            data = response.json()
            is_verified = data.get("status", False)

            # --- LARAVEL LOGIC REPLICATION ---
            # If Verified: Clear Lock & Unlock Device
            if response.status_code == 200 and is_verified:
                try:
                    # 1. Delete Security Reports (Lock)
                    db.execute(
                        text("DELETE FROM security_reports WHERE type = 'FACE_LIVENESS_LOCK' AND nik = :nik"), 
                        {"nik": nik}
                    )
                    
                    # 2. Unlock Karyawan Device
                    db.execute(
                        text("UPDATE karyawan SET lock_device_login = '0' WHERE nik = :nik"), 
                        {"nik": nik}
                    )
                    
                    db.commit()
                except Exception as db_e:
                    print(f"DB Error clearing lock: {db_e}")
                    # Continue anyway, don't fail the verification
            
            # Return Flask respose merged with status message, matching Android VerifyFaceResponse
            # Android expects: status, message, best_distance, best_ref, threshold
            response_payload = data.copy()
            response_payload["status"] = is_verified
            response_payload["message"] = "Verifikasi Wajah Berhasil" if is_verified else "Wajah Tidak Dikenali"
            
            return response_payload
            
    except httpx.RequestError as e:
        print(f"Connection Error to Flask: {e}")
        return {
            "status": False,
            "message": "Face Recognition Service Unavailable (Connection Error)"
        }
    except Exception as e:
        print(f"Internal Proxy Error: {e}")
        return {
            "status": False,
            "message": "Internal Proxy Error",
            "detail": str(e)
        }
