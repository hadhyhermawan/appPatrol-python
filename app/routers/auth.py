from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse, UserData
from app.models.models import Users, LoginLogs, PengaturanUmum
from typing import Optional
from app.core.security import verify_password
from jose import jwt
from app.core.security import SECRET_KEY, ALGORITHM
from datetime import datetime, timedelta

# Create token function
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=60 * 24 * 30) # 30 days
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

router = APIRouter(
    prefix="/api",
    tags=["Auth"]
)

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        # 1. Cari user
        user = db.query(Users).filter(Users.username == request.username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login gagal, username atau password salah",
            )
        
        # 2. Verify Password (check bcrypt hash)
        if not verify_password(request.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login gagal, username atau password salah",
            )
        
        # 3. Check if user has 'karyawan' role - they cannot login to web backend
        user_roles = db.execute(
            text("""
                SELECT r.name 
                FROM model_has_roles mhr
                JOIN roles r ON mhr.role_id = r.id
                WHERE mhr.model_id = :user_id 
                AND mhr.model_type = 'App\\\\Models\\\\User'
            """),
            {"user_id": user.id}
        ).fetchall()
        
        role_names = [row[0] for row in user_roles]
        
        # Block karyawan role from web login
        if 'karyawan' in role_names and len(role_names) == 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akses ditolak. Role 'karyawan' hanya dapat menggunakan aplikasi mobile.",
            )
        
        # 4. Handle device login logic (TODO: Implement full logic later)
        
        # 4. Create Token
        access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
        
        # 5. Log Login
        log = LoginLogs(
            user_id=user.id,
            ip="127.0.0.1", # TODO: Get real IP from request
            device=request.device_model or "Unknown",
            android_version=request.android_version,
            login_at=datetime.utcnow()
        )
        db.add(log)
        db.commit()
        
        # 6. Get settings
        settings = db.query(PengaturanUmum).first()
        face_fail_limit = settings.face_check_liveness_limit if settings else 3

        # 7. Get Karyawan data
        # Using raw SQL for performance and to handle legacy schema
        result = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user.id}).fetchone()
        nik = result[0] if result else None
        
        nama_karyawan = None
        if nik:
            karyawan_res = db.execute(text("SELECT nama_karyawan FROM karyawan WHERE nik = :nik"), {"nik": nik}).fetchone()
            nama_karyawan = karyawan_res[0] if karyawan_res else None

        # 8. Last Logins
        last_logins = db.query(LoginLogs).filter(LoginLogs.user_id == user.id).order_by(LoginLogs.login_at.desc()).limit(5).all()
        formatted_logins = []
        for l in last_logins:
            formatted_logins.append({
                "ip": l.ip, 
                "device": l.device, 
                "login_at": l.login_at.strftime("%Y-%m-%d %H:%M:%S") if l.login_at else None
            })

        # 9. WS URL
        ws_url = f"wss://k3guard.com/wss/?token={access_token}"

        return LoginResponse(
            message="Login berhasil",
            token=access_token,
            ws_url=ws_url,
            data=UserData(
                id_user=user.id,
                username=user.username,
                nik=nik,
                nama_karyawan=nama_karyawan,
                last_logins=formatted_logins,
                face_fail_limit=face_fail_limit
            ),
            walkie={} # Empty for now
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        # Log to server console/file but hide details from client
        print(f"ERROR LOGIN: {str(e)}") 
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )
