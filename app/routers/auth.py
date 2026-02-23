from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schemas.auth import LoginRequest, LoginResponse, UserData
from app.models.models import Users, LoginLogs, PengaturanUmum, Karyawan
from typing import Optional
from app.core.security import verify_password, get_password_hash
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
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

router = APIRouter(
    prefix="/api",
    tags=["Auth"]
)

@router.post("/login", response_model=LoginResponse)
async def login(req: Request, request: LoginRequest, db: Session = Depends(get_db)):
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

        # 2b. Auto-migrate legacy passwords (plain text) to bcrypt
        # If verify_password succeeded but hash doesn't look like bcrypt, update it
        if user.password and not (user.password.startswith("$2y$") or user.password.startswith("$2b$") or user.password.startswith("$2a$")):
            user.password = get_password_hash(request.password)
            db.add(user)
            db.commit()
        
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
        real_ip = req.headers.get("x-forwarded-for", req.client.host if req.client else "127.0.0.1")
        if real_ip:
            real_ip = real_ip.split(",")[0].strip()

        log = LoginLogs(
            user_id=user.id,
            ip=real_ip[:45],
            device=request.device_model or "Unknown",
            android_version=request.android_version,
            login_at=datetime.utcnow() + timedelta(hours=7)
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

@router.get("/auth/me")
async def get_current_user(
    db: Session = Depends(get_db), 
    authorization: Optional[str] = Header(None)
):
    """Get current user's information including roles and permissions"""
    try:
        # Extract token from Authorization header
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated"
            )
        
        token = authorization.replace("Bearer ", "")
        
        # Decode token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = int(payload.get("sub"))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Get user
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Session Reset Logic: Check if token is older than user's last update
        if "iat" in payload and user.updated_at:
            token_iat = payload["iat"]
            token_dt = datetime.fromtimestamp(token_iat)
            if token_dt < (user.updated_at - timedelta(seconds=2)):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired (Reset), please login again",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        # Get user's roles
        roles_result = db.execute(
            text("""
                SELECT r.id, r.name, r.guard_name
                FROM model_has_roles mhr
                JOIN roles r ON mhr.role_id = r.id
                WHERE mhr.model_id = :user_id 
                AND mhr.model_type = 'App\\\\Models\\\\User'
            """),
            {"user_id": user.id}
        ).fetchall()
        
        roles = [{"id": row[0], "name": row[1], "guard_name": row[2]} for row in roles_result]
        
        # Get user's permissions (through roles)
        permissions_result = db.execute(
            text("""
                SELECT DISTINCT p.id, p.name, p.guard_name
                FROM model_has_roles mhr
                JOIN role_has_permissions rhp ON mhr.role_id = rhp.role_id
                JOIN permissions p ON rhp.permission_id = p.id
                WHERE mhr.model_id = :user_id 
                AND mhr.model_type = 'App\\\\Models\\\\User'
                ORDER BY p.name
            """),
            {"user_id": user.id}
        ).fetchall()
        
        permissions = [{"id": row[0], "name": row[1], "guard_name": row[2]} for row in permissions_result]
        
        return {
            "id": user.id,
            "username": user.username,
            "roles": roles,
            "permissions": permissions
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"ERROR GET CURRENT USER: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error"
        )

# Profile endpoints
from fastapi import UploadFile, File, Form
from app.core.security import get_password_hash
import os
import shutil
from pathlib import Path

@router.get("/auth/profile")
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user profile"""
    try:
        user_id = current_user["id"]
        
        # Get user data
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get roles
        roles = db.execute(
            text("""
                SELECT r.name 
                FROM model_has_roles mhr
                JOIN roles r ON mhr.role_id = r.id
                WHERE mhr.model_id = :user_id
            """),
            {"user_id": user_id}
        ).fetchall()
        role_list = [r[0] for r in roles]
        
        # Get permissions
        permissions = []
        if "Super Admin" in role_list:
            permissions = ["*"]
        else:
            perms = db.execute(
                text("""
                    SELECT DISTINCT p.name
                    FROM role_has_permissions rhp
                    JOIN permissions p ON rhp.permission_id = p.id
                    JOIN model_has_roles mhr ON rhp.role_id = mhr.role_id
                    WHERE mhr.model_id = :user_id
                """),
                {"user_id": user_id}
            ).fetchall()
            permissions = [p[0] for p in perms]
        
        # Construct photo URL if exists
        photo_url = None
        if user.foto:
            from os import getenv
            base_url = getenv("BASE_URL", "https://k3guard.com")
            photo_url = f"{base_url}/storage/users/{user.foto}"
        
        return {
            "status": True,
            "data": {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "address": user.address,
                "photo": photo_url,
                "roles": role_list,
                "permissions": permissions,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR GET PROFILE: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/auth/profile")
async def update_profile(
    name: Optional[str] = Form(None),
    username: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    
    # Extra fields for Karyawan compatibility
    nama_karyawan: Optional[str] = Form(None),
    no_ktp: Optional[str] = Form(None),
    no_hp: Optional[str] = Form(None),
    alamat: Optional[str] = Form(None),
    
    # Photo might be 'photo' or 'foto'
    photo: Optional[UploadFile] = File(None),
    foto: Optional[UploadFile] = File(None),
    
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile (Sync with Karyawan data if linked)"""
    try:
        user_id = current_user["id"]
        
        # Get user
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # Determine actual file upload (priority to 'foto' if both present, or 'photo')
        upload_file = foto if foto else photo
        
        # Check if user is linked to Karyawan
        # Use raw SQL as in login logic
        result = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user.id}).fetchone()
        nik = result[0] if result else None
        
        # Logic for Karyawan
        user_foto_name = None
        
        if nik:
            karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
            if karyawan:
                # Update Karyawan Data
                # Prioritize specific fields (nama_karyawan) then fallback to generic (name)
                # Note: PHP uses nama_karyawan form input.
                
                update_data = {}
                if nama_karyawan: update_data['nama_karyawan'] = nama_karyawan
                elif name: update_data['nama_karyawan'] = name
                
                if no_ktp: update_data['no_ktp'] = no_ktp
                
                if no_hp: update_data['no_hp'] = no_hp
                elif phone: update_data['no_hp'] = phone
                
                if alamat: update_data['alamat'] = alamat
                elif address: update_data['alamat'] = address
                
                # Apply updates
                for key, val in update_data.items():
                    setattr(karyawan, key, val)
                
                # Handle Photo for Karyawan
                if upload_file:
                    destination_path = Path("/var/www/appPatrol/storage/app/public/karyawan")
                    destination_path.mkdir(parents=True, exist_ok=True)
                    
                    # Naming: NIK.ext
                    file_extension = upload_file.filename.split(".")[-1]
                    # PHP uses getClientOriginalExtension(), verify if we trust generic extension or assume defaults
                    if not file_extension: file_extension = "jpg"
                    
                    foto_name = f"{nik}.{file_extension}"
                    file_path = destination_path / foto_name
                    
                    # Delete old if exists
                    if karyawan.foto:
                         old_path = destination_path / karyawan.foto
                         if old_path.exists():
                             os.remove(old_path)
                             
                    # Save new
                    upload_file.file.seek(0)
                    with open(file_path, "wb") as buffer:
                        shutil.copyfileobj(upload_file.file, buffer)
                        
                    karyawan.foto = foto_name
                    
                db.add(karyawan)
                
        # Logic for User (Always update user table too)
        # Name: PHP uses nama_karyawan if filled, else user->name.
        if nama_karyawan: user.name = nama_karyawan
        elif name: user.name = name
        
        if email: user.email = email
        if username: user.username = username
        # user.phone and user.address - PHP doesn't explicitly update these in 'userUpdateData' array but let's keep Python logic
        if phone: user.phone = phone
        if address: user.address = address
        
        # Handle Photo for User (If NOT Karyawan OR logic dictates separate user photo?)
        # PHP Logic: 
        # } elseif ($request->hasFile('foto')) { destination = 'public/users'; ... }
        # So only save to User photo if NOT Karyawan.
        
        if not nik and upload_file:
             destination_path = Path("/var/www/appPatrol/storage/app/public/users")
             destination_path.mkdir(parents=True, exist_ok=True)
             
             file_extension = upload_file.filename.split(".")[-1]
             if not file_extension: file_extension = "jpg"
             
             foto_name = f"USR_{user.id}.{file_extension}"
             file_path = destination_path / foto_name
             
             if user.foto:
                 old_path = destination_path / user.foto
                 if old_path.exists():
                     os.remove(old_path)
            
             upload_file.file.seek(0)
             with open(file_path, "wb") as buffer:
                 shutil.copyfileobj(upload_file.file, buffer)
                 
             user.foto = foto_name
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Fetch updated roles/permissions for response
        roles = db.execute(text("SELECT r.name FROM model_has_roles mhr JOIN roles r ON mhr.role_id = r.id WHERE mhr.model_id = :uid"), {"uid": user.id}).fetchall()
        role_list = [r[0] for r in roles]
        
        permissions = []
        if "Super Admin" in role_list:
            permissions = ["*"]
        else:
            perms = db.execute(text("SELECT DISTINCT p.name FROM role_has_permissions rhp JOIN permissions p ON rhp.permission_id = p.id JOIN model_has_roles mhr ON rhp.role_id = mhr.role_id WHERE mhr.model_id = :uid"), {"uid": user.id}).fetchall()
            permissions = [p[0] for p in perms]
            
        # Construct response
        from os import getenv
        base_url = getenv("BASE_URL", "https://k3guard.com")
        
        photo_url = None
        # Display photo. If Karyawan, use Karyawan photo?
        # User Logic currently uses user.foto.
        # But if we didn't update user.foto because they are Karyawan, what shows up?
        # PHP Profile logic:
        # $karyawan = ...; $data['karyawan'] = $karyawan; ... view('profile.index', $data)
        # The view likely shows Karyawan photo if available.
        # Python get_profile: return { data: { photo: ... } }
        # Let's check get_profile logic in Python later if needed. For now, update logic is consistent with PHP write behavior.
        
        if user.foto:
             photo_url = f"{base_url}/storage/users/{user.foto}"
        # If user is karyawan and has no user photo but has karyawan photo?
        # That's a get_profile concern.
        
        return {
            "status": True,
            "message": "Profile updated successfully",
            "data": {
                "id": user.id,
                "username": user.username,
                "name": user.name,
                "email": user.email,
                "phone": user.phone,
                "address": user.address,
                "photo": photo_url,
                "roles": role_list,
                "permissions": permissions,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR UPDATE PROFILE: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    try:
        user_id = current_user["id"]
        
        # Get user
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify current password
        if not verify_password(current_password, user.password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Update password
        user.password = get_password_hash(new_password)
        db.commit()
        
        return {
            "status": True,
            "message": "Password changed successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"ERROR CHANGE PASSWORD: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
