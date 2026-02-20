from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import text, select
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import datetime
from jose import jwt
from app.database import get_db
from app.models.models import Users, Karyawan, LoginLogs, PengaturanUmum, WalkieChannels, WalkieChannelCabangs
from app.core.security import verify_password, get_password_hash # Pakai util security yg sdh ada
from app.core.security import SECRET_KEY, ALGORITHM # Pakai config yg sdh ada
import hashlib
from app.models.models import PersonalAccessTokens

# Router khusus untuk Migrasi Android (Tanpa Blocking Karyawan)
router = APIRouter(
    prefix="/api/android", # Prefix sementara agar tidak bentrok dengan /api/login web
    tags=["Auth Legacy (Android)"],
    responses={404: {"description": "Not found"}},
)

# --- SCHEMAS (Sesuai LoginResponse.kt) ---
class AndroidLoginRequest(BaseModel):
    username: str
    password: str
    device_model: Optional[str] = None
    android_version: Optional[str] = None

class UserDataAndroid(BaseModel):
    id_user: int
    username: str
    nik: Optional[str] = None
    nama_karyawan: Optional[str] = None
    last_logins: Optional[List[Dict[str, Any]]] = None
    face_fail_limit: Optional[int] = 3

class WalkieInfoAndroid(BaseModel):
    channels: List[Dict[str, Any]] = []
    default_channel: Optional[Dict[str, Any]] = None
    ws_base: Optional[str] = None

class AndroidLoginResponse(BaseModel):
    message: str
    token: str
    ws_url: Optional[str] = None
    data: Optional[UserDataAndroid] = None

    walkie: Optional[WalkieInfoAndroid] = None

class CurrentUser(BaseModel):
    id: int
    username: str
    nik: Optional[str] = None

# --- TOKEN UTIL ---
def create_android_token(data: dict):
    # Token Long-lived untuk Android (misal 3 bulan)
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=90)
    to_encode = data.copy()
    to_encode.update({"exp": expire, "iat": datetime.datetime.utcnow(), "scope": "android"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_allowed_channels_helper(db: Session, nik: str):
    karyawan = db.query(Karyawan).filter(Karyawan.nik == nik).first()
    if not karyawan: return []
    kode_cabang = karyawan.kode_cabang
    kode_dept = karyawan.kode_dept
    channels = db.query(WalkieChannels).filter(WalkieChannels.active == 1).all()
    allowed = []
    for c in channels:
        if c.dept_members:
            depts = [d.strip() for d in c.dept_members.split(',')]
            if kode_dept not in depts: continue
        
        channel_cabangs = db.query(WalkieChannelCabangs).filter(WalkieChannelCabangs.walkie_channel_id == c.id).all()
        allowed_cabangs = [cc.kode_cabang for cc in channel_cabangs]
        
        if allowed_cabangs and kode_cabang not in allowed_cabangs: continue
            
        allowed.append(c)
    
    allowed.sort(key=lambda x: (x.priority, x.name))
    return sorted(allowed, key=lambda x: x.priority, reverse=True)


# --- SANCTUM VALIDATION ---
def validate_sanctum_token(db: Session, token: str):
    """
    Validasi Token Sanctum (Laravel Personal Access Token)
    Format: id|random_string
    """
    if "|" not in token:
        return None
        
    try:
        token_id, token_value = token.split("|", 1)
        # Cari token by ID
        pat = db.query(PersonalAccessTokens).filter(PersonalAccessTokens.id == token_id).first()
        if not pat:
            return None
            
        # Validasi Hash (SHA256)
        hashed_value = hashlib.sha256(token_value.encode()).hexdigest()
        if pat.token == hashed_value:
            # Token Valid -> Return User ID
            return pat.tokenable_id
            
    except Exception as e:
        print(f"Sanctum validation error: {e}")
        
    return None

def get_current_user_sanctum(
    authorization: Optional[str] = Header(None), 
    db: Session = Depends(get_db)
) -> CurrentUser:
    """
    Auth Dependency yang support JWT (Baru) DAN Sanctum (Lama/Android).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Token Required")
    
    token = authorization.replace("Bearer ", "").strip()
    user_id = None
    username = None

    # 1. Coba JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        username = payload.get("username") # Bisa none klo JWT lama
    except Exception:
        # 2. Jika Gagal JWT, Coba Sanctum
        user_id = validate_sanctum_token(db, token)
        
    if not user_id:
        raise HTTPException(status_code=401, detail="Token Invalid/Expired")
        
    # Cari User Detail
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User Not Found")
        
    # Cari NIK
    nik = None
    pivot = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user.id}).fetchone()
    if pivot:
        nik = pivot[0]
        
    # Fallback NIK
    if not nik and user.username.isdigit() and len(user.username) > 5:
         nik = user.username
         
    return CurrentUser(
        id=user.id,
        username=user.username,
        nik=nik
    )

# --- ENDPOINTS ---

from fastapi import Form

@router.post("/login", response_model=AndroidLoginResponse)
async def login_android(
    username: str = Form(...), 
    password: str = Form(...),
    device_model: Optional[str] = Form(None),
    android_version: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    x_app_version: Optional[str] = Header(None, alias="X-App-Version")
):
    """
    Endpoint Login khusus Aplikasi Android (Jalur Postman/Form Data).
    Tidak memblokir role 'karyawan'.
    Mengembalikan struktur JSON yang kompatibel dengan GuardSystemApp.
    """
    # Compatibility Wrapper
    login_data = AndroidLoginRequest(
        username=username,
        password=password,
        device_model=device_model,
        android_version=android_version
    )
    # 1. Cari User
    stmt = select(Users).where((Users.username == login_data.username) | (Users.email == login_data.username))
    user = db.execute(stmt).scalars().first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail={"code": "USER_NOT_FOUND", "message": "Username tidak ditemukan. Periksa kembali username Anda."}
        )

    # 2. Verify Password
    if not verify_password(login_data.password, user.password):
        raise HTTPException(
            status_code=401,
            detail={"code": "WRONG_PASSWORD", "message": "Password salah. Silakan coba lagi."}
        )

    # 3. Cek status akun (opsional jika ada field active/status)
    if hasattr(user, 'active') and user.active == 0:
        raise HTTPException(
            status_code=403,
            detail={"code": "ACCOUNT_INACTIVE", "message": "Akun Anda tidak aktif. Hubungi administrator."}
        )
    
    # Auto-update hash jika legacy (non-bcrypt) - optional safety
    if user.password and not user.password.startswith("$2"):
        user.password = get_password_hash(login_data.password)
        db.add(user)
        db.commit()

    # 3. Ambil Data Karyawan (NIK & Nama)
    # Relasi manual via query
    nik = None
    nama_karyawan = None
    
    # Coba cari di users_karyawan (table pivot yg mungkin ada di Laravel structure)
    try:
        pivot = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user.id}).fetchone()
        if pivot:
            nik = pivot[0]
            
        if nik:
            kary = db.execute(text("SELECT nama_karyawan FROM karyawan WHERE nik = :nik"), {"nik": nik}).fetchone()
            if kary:
                nama_karyawan = kary[0]
    except Exception:
        # Fallback jika tabel users_karyawan belum ada di model/db
        pass

    # 4. Ambil Settings (Face Limit)
    face_fail_limit = 3
    try:
        setting = db.query(PengaturanUmum).first()
        if setting:
            face_fail_limit = setting.face_check_liveness_limit
    except Exception:
        pass

    # 5. Log Login
    try:
        log = LoginLogs(
            user_id=user.id,
            ip="127.0.0.1", # TODO: Real IP
            device=login_data.device_model or "Unknown",
            android_version=login_data.android_version,
            login_at=datetime.datetime.utcnow()
        )
        db.add(log)
        db.commit()
    except Exception:
        pass # Jangan gagalkan login cuma gara-gara log error

    # 6. Generate Token
    access_token = create_android_token({"sub": str(user.id), "username": user.username})

    # 7. Siapkan WS URL (Link ke Python Socket.IO)
    # Walkie Talkie Raw WebSocket (Port 8081 via Nginx /walkie-ws/)
    # Fix: Point to Raw WS, NOT Python Socket.IO
    ws_url = f"wss://frontend.k3guard.com/walkie-ws"
    
    # 8. Last Logins (Dummy/Real)
    last_logins = []
    
    # 9. Return Response
    walkie_channels_list = []
    default_channel_obj = None
    
    if nik:
        try:
            allowed = get_allowed_channels_helper(db, nik)
            for c in allowed:
                c_data = {
                    "id": c.id,
                    "code": c.code,
                    "name": c.name,
                    "active": c.active,
                    "auto_join": c.auto_join,
                    "is_default": 1 if c.auto_join == 1 else 0
                }
                walkie_channels_list.append(c_data)
            
            # Default logic
            for c in walkie_channels_list:
                if c['auto_join'] == 1:
                    default_channel_obj = c
                    break
            
            if not default_channel_obj and walkie_channels_list:
                default_channel_obj = walkie_channels_list[0]
                
        except Exception as e:
            print(f"Error getting walkie channels: {e}", flush=True)

    return AndroidLoginResponse(
        message="Login Berhasil",
        token=access_token,
        ws_url=ws_url,
        data=UserDataAndroid(
            id_user=user.id,
            username=user.username,
            nik=nik,
            nama_karyawan=nama_karyawan or user.name,
            last_logins=last_logins,
            face_fail_limit=face_fail_limit
        ),
        walkie=WalkieInfoAndroid(
            channels=walkie_channels_list,
            default_channel=default_channel_obj,
            ws_base=ws_url
        )
    )

@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    # Stateless JWT cannot really be invalidated server-side without blacklist.
    # Just return success.
    return {"message": "Logout Berhasil"}


# --- DEPENDENCY FOR OTHER ROUTERS ---
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/android/login")

def get_current_user_nik(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token Required")
    
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        
        # Cari NIK
        pivot = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user_id}).fetchone()
        if pivot:
            return pivot[0]
            
        # Fallback Username
        user = db.query(Users).filter(Users.id == user_id).first()
        if user:
             k = db.query(Karyawan).filter(Karyawan.nik == user.username).first()
             if k:
                 return k.nik
                 
        raise HTTPException(status_code=404, detail="Data Karyawan Tidak Ditemukan")

    except Exception:
        raise HTTPException(status_code=401, detail="Token Invalid/Expired")

def get_current_user_data(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> CurrentUser:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token Required")
    
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        username = payload.get("username")
        
        # Cari NIK
        pivot = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user_id}).fetchone()
        nik = pivot[0] if pivot else None
            
        if not nik:
            # Fallback Username
            user = db.query(Users).filter(Users.id == user_id).first()
            if user:
                 k = db.query(Karyawan).filter(Karyawan.nik == user.username).first()
                 if k:
                     nik = k.nik
        
        # Jika NIK tetap None, mungkin admin/non-karyawan. Tetap return user data.
        return CurrentUser(id=int(user_id), username=username, nik=nik)

    except Exception as e:
        raise HTTPException(status_code=401, detail="Token Invalid/Expired")

@router.get("/validate-user")
async def validate_user_token_endpoint(token: str, db: Session = Depends(get_db)):
    """
    Endpoint internal untuk Node.js Service memvalidasi token Android.
    """
    try:
        # Decode Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        username = payload.get("username")
        
        # Cari User Valid
        user = db.query(Users).filter(Users.id == user_id).first()
        if not user:
             return {"status": False, "message": "User not found"}

        # Cari Data Karyawan (NIK & Nama)
        nik = None
        nama = user.name
        
        try:
            pivot = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user.id}).fetchone()
            if pivot:
                nik = pivot[0]
                kary = db.execute(text("SELECT nama_karyawan FROM karyawan WHERE nik = :nik"), {"nik": nik}).fetchone()
                if kary:
                    nama = kary[0]
            
            # Fallback NIK dari username
            if not nik and user.username.isdigit() and len(user.username) > 5:
                 nik = user.username
                 
        except:
            pass
            
        return {
            "status": True,
            "user": {
                "id": user.id,
                "nik": nik or user.username, # Penting: Walkie butuh NIK
                "name": nama
            }
        }
            
    except Exception as e:
        # Jika JWT Gagal, Coba Fallback ke Sanctum
        try:
            sanctum_user_id = validate_sanctum_token(db, token)
            if sanctum_user_id:
                user = db.query(Users).filter(Users.id == sanctum_user_id).first()
                if user:
                    nik = None
                    nama = user.name
                    
                    pivot = db.execute(text("SELECT nik FROM users_karyawan WHERE id_user = :uid"), {"uid": user.id}).fetchone()
                    if pivot:
                        nik = pivot[0]
                        kary = db.execute(text("SELECT nama_karyawan FROM karyawan WHERE nik = :nik"), {"nik": nik}).fetchone()
                        if kary:
                            nama = kary[0]
                    
                    if not nik and user.username.isdigit() and len(user.username) > 5:
                        nik = user.username

                    return {
                        "status": True,
                        "user": {
                            "id": user.id,
                            "nik": nik or user.username,
                            "name": nama
                        }
                    }
        except Exception as se:
            pass

        return {"status": False, "message": str(e)}
