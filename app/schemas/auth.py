from pydantic import BaseModel
from typing import Optional, List, Any

class LoginRequest(BaseModel):
    username: str
    password: str
    device_model: Optional[str] = None
    android_version: Optional[str] = None

class UserData(BaseModel):
    id_user: int
    username: str
    nik: Optional[str]
    nama_karyawan: Optional[str]
    last_logins: List[Any]
    face_fail_limit: int

class LoginResponse(BaseModel):
    message: str
    token: str
    ws_url: str
    data: UserData
    walkie: Optional[dict] = None
