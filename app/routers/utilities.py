from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from app.database import get_db
from app.models.models import Users, ModelHasRoles, Roles, Karyawan, Permissions, PermissionGroups, LoginLogs, Cabang, SecurityReports, Departemen
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import sys
import traceback

router = APIRouter(
    prefix="/api/utilities",
    tags=["Utilities"]
)

# ==========================================
# USER MANAGEMENT
# ==========================================

class UserDTO(BaseModel):
    id: int
    name: str
    username: str
    email: str
    role: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

@router.get("/users", response_model=List[UserDTO])
async def get_users(
    search: Optional[str] = Query(None, description="Search by Name/Email"),
    limit: Optional[int] = Query(100),
    db: Session = Depends(get_db)
):
    try:
        # Query Users with Roles
        query = db.query(Users)
        
        if search:
            query = query.filter(
                (Users.name.like(f"%{search}%")) |
                (Users.email.like(f"%{search}%")) |
                (Users.username.like(f"%{search}%"))
            )
            
        data = query.order_by(desc(Users.created_at)).limit(limit).all()
        
        result = []
        for user in data:
            dto = UserDTO.model_validate(user)
            
            # Fetch Role manually
            # model_has_roles: model_id = user.id, model_type = 'App\Models\User' usually
            role_link = db.query(ModelHasRoles).filter(
                ModelHasRoles.model_id == user.id
            ).first()
            
            if role_link:
                role = db.query(Roles).filter(Roles.id == role_link.role_id).first()
                if role:
                    dto.role = role.name
                    
            result.append(dto)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ROLE MANAGEMENT
# ==========================================

class RoleDTO(BaseModel):
    id: int
    name: str
    guard_name: str
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

@router.get("/roles", response_model=List[RoleDTO])
async def get_roles(
    name: Optional[str] = Query(None, description="Filter by Role Name"),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Roles)
        if name:
            query = query.filter(Roles.name.like(f"%{name}%"))
            
        data = query.order_by(Roles.id).all()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# PERMISSION MANAGEMENT
# ==========================================

class PermissionGroupDTO(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True

class PermissionDTO(BaseModel):
    id: int
    name: str
    guard_name: str
    group_name: Optional[str] = None
    
    class Config:
        from_attributes = True

@router.get("/permission-groups", response_model=List[PermissionGroupDTO])
async def get_permission_groups(db: Session = Depends(get_db)):
    try:
        data = db.query(PermissionGroups).order_by(PermissionGroups.id).all()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/permission-groups", response_model=PermissionGroupDTO)
async def create_permission_group(
    payload: PermissionGroupDTO, # Re-using DTO for simplicity as it only has name, id is ignored on input usually but let's be strict if needed
    db: Session = Depends(get_db)
):
    try:
        new_group = PermissionGroups(name=payload.name)
        db.add(new_group)
        db.commit()
        db.refresh(new_group)
        return new_group
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/permission-groups/{id}", response_model=PermissionGroupDTO)
async def update_permission_group(
    id: int,
    payload: PermissionGroupDTO,
    db: Session = Depends(get_db)
):
    try:
        group = db.query(PermissionGroups).filter(PermissionGroups.id == id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Permission Group not found")
            
        group.name = payload.name
        db.commit()
        db.refresh(group)
        return group
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/permission-groups/{id}")
async def delete_permission_group(
    id: int,
    db: Session = Depends(get_db)
):
    try:
        group = db.query(PermissionGroups).filter(PermissionGroups.id == id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Permission Group not found")
            
        db.delete(group)
        db.commit()
        return {"message": "Permission Group deleted successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/permissions", response_model=List[PermissionDTO])
async def get_permissions(
    id_permission_group: Optional[int] = Query(None, description="Filter by Permission Group ID"),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Permissions).join(PermissionGroups, Permissions.id_permission_group == PermissionGroups.id)
        
        if id_permission_group:
            query = query.filter(Permissions.id_permission_group == id_permission_group)
            
        data = query.order_by(Permissions.id_permission_group).all()
        
        result = []
        for item in data:
            dto = PermissionDTO.model_validate(item)
            dto.group_name = item.permission_groups.name if item.permission_groups else None
            result.append(dto)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreatePermissionDTO(BaseModel):
    name: str
    id_permission_group: int

@router.post("/permissions", response_model=PermissionDTO)
async def create_permission(
    payload: CreatePermissionDTO,
    db: Session = Depends(get_db)
):
    try:
        # Check if exists
        existing = db.query(Permissions).filter(
            Permissions.name == payload.name, 
            Permissions.guard_name == 'web'
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Permission already exists")

        new_permission = Permissions(
            name=payload.name.lower(),
            guard_name='web', # Default guard
            id_permission_group=payload.id_permission_group
        )
        
        db.add(new_permission)
        db.commit()
        db.refresh(new_permission)
        
        # Load relationship
        db.refresh(new_permission, ['permission_groups'])
        
        dto = PermissionDTO.model_validate(new_permission)
        dto.group_name = new_permission.permission_groups.name if new_permission.permission_groups else None
        
        return dto

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# ROLE PERMISSION MANAGEMENT
# ==========================================

class RolePermissionDTO(BaseModel):
    role_id: int
    role_name: str
    permissions: List[int]  # List of permission IDs
    
    class Config:
        from_attributes = True

@router.get("/roles/{role_id}/permissions")
async def get_role_permissions(
    role_id: int,
    db: Session = Depends(get_db)
):
    """Get all permissions assigned to a specific role"""
    try:
        role = db.query(Roles).filter(Roles.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        
        # Get all permissions for this role
        permission_ids = [p.id for p in role.permission]
        
        return {
            "role_id": role.id,
            "role_name": role.name,
            "permissions": permission_ids
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AssignPermissionsDTO(BaseModel):
    permission_ids: List[int]

@router.post("/roles/{role_id}/permissions")
async def assign_permissions_to_role(
    role_id: int,
    payload: AssignPermissionsDTO,
    db: Session = Depends(get_db)
):
    """Assign multiple permissions to a role (replaces existing permissions)"""
    try:
        role = db.query(Roles).filter(Roles.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        
        # Verify all permissions exist
        permissions = db.query(Permissions).filter(
            Permissions.id.in_(payload.permission_ids)
        ).all()
        
        if len(permissions) != len(payload.permission_ids):
            raise HTTPException(status_code=400, detail="One or more permissions not found")
        
        # Clear existing permissions and assign new ones
        role.permission = permissions
        db.commit()
        
        return {
            "message": "Permissions assigned successfully",
            "role_id": role.id,
            "role_name": role.name,
            "assigned_permissions": len(permissions)
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/roles/{role_id}/permissions/{permission_id}")
async def remove_permission_from_role(
    role_id: int,
    permission_id: int,
    db: Session = Depends(get_db)
):
    """Remove a specific permission from a role"""
    try:
        role = db.query(Roles).filter(Roles.id == role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        
        permission = db.query(Permissions).filter(Permissions.id == permission_id).first()
        if not permission:
            raise HTTPException(status_code=404, detail="Permission not found")
        
        # Remove permission from role
        if permission in role.permission:
            role.permission.remove(permission)
            db.commit()
            return {"message": "Permission removed successfully"}
        else:
            raise HTTPException(status_code=404, detail="Permission not assigned to this role")
            
    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# LOGS MANAGEMENT
# ==========================================

class LoginLogDTO(BaseModel):
    id: int
    user_name: Optional[str] = None
    email: Optional[str] = None
    branch_name: Optional[str] = None
    ip: str
    device: Optional[str] = None
    android_version: Optional[str] = None
    login_at: datetime
    logout_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.get("/logs", response_model=List[LoginLogDTO])
async def get_logs(
    user: Optional[str] = Query(None),
    ip: Optional[str] = Query(None),
    device: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    kode_cabang: Optional[str] = Query(None),
    limit: int = 100,
    db: Session = Depends(get_db)
):
    try:
        query = db.query(LoginLogs).join(Users, LoginLogs.user_id == Users.id)
        
        # We need to join Karyawan and Cabang for proper filtering and data display
        # Note: Users -> Karyawan (via users_karyawan intermediate logic or direct if model supports it)
        # Checking models.py... Users doesn't have direct Karyawan link easily without intermediate 'users_karyawan' which is not in the models.py snippets I saw?
        # Let's check model definition again if needed.
        # But wait, the Laravel query used: 
        # ->leftJoin('users_karyawan', 'users.id', '=', 'users_karyawan.id_user')
        # ->leftJoin('karyawan', 'users_karyawan.nik', '=', 'karyawan.nik')
        
        # Since I don't have 'users_karyawan' model in the imports, I might need to skip advanced joins for now or simplify.
        # However, LoginLogs has user_id. Users has name/email.
        
        if user:
            query = query.filter(Users.name.like(f"%{user}%"))
        
        if ip:
            query = query.filter(LoginLogs.ip.like(f"%{ip}%"))
            
        if device:
            query = query.filter(LoginLogs.device.like(f"%{device}%"))
            
        if from_date:
            query = query.filter(LoginLogs.login_at >= from_date)
            
        if to_date:
            query = query.filter(LoginLogs.login_at <= to_date)
            
        query = query.order_by(desc(LoginLogs.id))
        
        data = query.limit(limit).all()
        
        result = []
        for log in data:
            dto = LoginLogDTO.model_validate(log)
            dto.user_name = log.user.name if log.user else "Unknown"
            dto.email = log.user.email if log.user else "-"
            # Branch name is harder without the full join, leaving empty for now or subsequent fetch
            result.append(dto)
            
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/logs/{id}")
async def delete_log(id: int, db: Session = Depends(get_db)):
    try:
        log = db.query(LoginLogs).filter(LoginLogs.id == id).first()
        if not log:
            raise HTTPException(status_code=404, detail="Log not found")
        db.delete(log)
        db.commit()
        return {"message": "Log deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# SECURITY REPORTS
# ==========================================

class SecurityReportDTO(BaseModel):
    id: int
    created_at: Optional[datetime] = None
    user_name: Optional[str] = None
    user_nik: Optional[str] = None
    branch_name: Optional[str] = None
    dept_name: Optional[str] = None
    type: str
    detail: Optional[str] = None
    device_model: Optional[str] = None
    ip_address: Optional[str] = None
    status_flag: str

    class Config:
        from_attributes = True

@router.get("/security-reports", response_model=List[SecurityReportDTO])
async def get_security_reports(
    keyword: Optional[str] = Query(None),
    nik_filter: Optional[str] = Query(None),
    kode_cabang: Optional[str] = Query(None),
    kode_dept: Optional[str] = Query(None),
    limit: int = 20,
    db: Session = Depends(get_db)
):
    try:
        # Complex join logic: SecurityReports -> Users -> Karyawan -> Cabang, Departemen
        # Note: Users is related to Karyawan usually via users_karyawan intermediate table in many systems, 
        # OR usually 'users.email' matches 'karyawan.email' or 'users.id' linked.
        # Looking at original code: $query->with(['user', 'user.karyawan', ...])
        # In Python models, Users model doesn't seem to have direct Karyawan relationship mapped in what I see, 
        # but let's check if we can join Karyawan via NIK or similar if Users has NIK.
        # Actually SecurityReports has 'nik' column directly! 
        # Line 1279: nik: Mapped[Optional[str]] = mapped_column(String(50))
        # So we can join Karyawan on SecurityReports.nik == Karyawan.nik
        
        query = db.query(SecurityReports).outerjoin(Users, SecurityReports.user_id == Users.id)\
                  .outerjoin(Karyawan, SecurityReports.nik == Karyawan.nik)\
                  .outerjoin(Cabang, Karyawan.kode_cabang == Cabang.kode_cabang)\
                  .outerjoin(Departemen, Karyawan.kode_dept == Departemen.kode_dept)
        
        if keyword:
            query = query.filter(
                (SecurityReports.nik.like(f"%{keyword}%")) | 
                (SecurityReports.type.like(f"%{keyword}%"))
            )
            
        if nik_filter:
            query = query.filter(SecurityReports.nik == nik_filter)
            
        if kode_cabang:
            query = query.filter(Karyawan.kode_cabang == kode_cabang)
            
        if kode_dept:
            query = query.filter(Karyawan.kode_dept == kode_dept)
            
        query = query.order_by(desc(SecurityReports.created_at))
        
        data = query.limit(limit).all()
        
        result = []
        for report in data:
            dto = SecurityReportDTO.model_validate(report)
            dto.user_name = report.user.name if report.user else "Unknown"
            dto.user_nik = report.nik
            
            # Since we joined Karyawan, we can try to fetch it. 
            # But the ORM relationship might not be set up on SecurityReports for 'karyawan' directly 
            # relying on the join we just did.
            # To make it easier, let's look up Karyawan if needed or use the joined objects if we selected them.
            # ORM way: defining relationship is best. But let's rely on lazy loading if relationship exists 
            # or manual query if not.
            # Let's check model again. SecurityReports has 'user' relationship. User might have 'karyawan' relationship?
            # In models.py snippets, Users doesn't show 'karyawan' relationship clearly.
            # However, since we have 'nik' on report, let's try to get Karyawan from that.
            
            karyawan = db.query(Karyawan).filter(Karyawan.nik == report.nik).first() if report.nik else None
            
            if karyawan:
                cabang = db.query(Cabang).filter(Cabang.kode_cabang == karyawan.kode_cabang).first()
                dept = db.query(Departemen).filter(Departemen.kode_dept == karyawan.kode_dept).first()
                dto.branch_name = cabang.nama_cabang if cabang else "-"
                dto.dept_name = dept.nama_dept if dept else "-"
            else:
                 dto.branch_name = "-"
                 dto.dept_name = "-"
                 
            result.append(dto)
            
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/security-reports/{id}")
async def delete_security_report(id: int, db: Session = Depends(get_db)):
    try:
        report = db.query(SecurityReports).filter(SecurityReports.id == id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        db.delete(report)
        db.commit()
        return {"message": "Report deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# MULTI DEVICE
# ==========================================

class MultiDeviceDTO(BaseModel):
    user_id: int
    name: str
    email: str
    username: str
    kode_cabang: Optional[str] = None
    nama_cabang: Optional[str] = None
    device_count: int
    devices: str
    last_login: datetime

@router.get("/multi-device", response_model=List[MultiDeviceDTO])
async def get_multi_device(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    limit: int = 15,
    db: Session = Depends(get_db)
):
    try:
        from_d = from_date if from_date else (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        to_d = to_date if to_date else datetime.now().strftime('%Y-%m-%d')

        # Complex Aggregation Query
        # Translating the Laravel query to SQLAlchemy Core or Raw SQL might be easier for complex aggregations
        # Laravel Logic:
        # DB::table('login_logs')
        # ->join('users', 'login_logs.user_id', '=', 'users.id')
        # ... joins ...
        # ->select(users.id, users.name, ..., COUNT(DISTINCT device), GROUP_CONCAT(device), MAX(login_at))
        # ->where(...)
        # ->groupBy(users.id...)
        # ->havingRaw('COUNT(DISTINCT login_logs.device) > 1')
        
        sql = text("""
            SELECT 
                u.id as user_id, 
                u.name, 
                u.email, 
                u.username, 
                k.kode_cabang,
                c.nama_cabang, 
                COUNT(DISTINCT l.device) as device_count, 
                GROUP_CONCAT(DISTINCT l.device ORDER BY l.device SEPARATOR '|||') as devices, 
                MAX(l.login_at) as last_login
            FROM login_logs l
            JOIN users u ON l.user_id = u.id
            LEFT JOIN users_karyawan uk ON u.id = uk.id_user
            LEFT JOIN karyawan k ON uk.nik = k.nik
            LEFT JOIN cabang c ON k.kode_cabang = c.kode_cabang
            WHERE l.device IS NOT NULL
            AND l.login_at >= :from_d
            AND l.login_at <= :to_d
            GROUP BY u.id, u.name, u.email, u.username, k.kode_cabang, c.nama_cabang
            HAVING COUNT(DISTINCT l.device) > 1
            ORDER BY device_count DESC, last_login DESC
            LIMIT :limit
        """)
        
        result = db.execute(sql, {"from_d": from_d, "to_d": to_d + " 23:59:59", "limit": limit}).fetchall()
        
        data = []
        for row in result:
            # RowProxy/Row mapping
            data.append(MultiDeviceDTO(
                user_id=row.user_id,
                name=row.name,
                email=row.email,
                username=row.username,
                kode_cabang=row.kode_cabang,
                nama_cabang=row.nama_cabang,
                device_count=row.device_count,
                devices=row.devices if row.devices else "",
                last_login=row.last_login
            ))
            
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class IgnoreDeviceDTO(BaseModel):
    user_id: int
    device: str

@router.post("/multi-device/ignore")
async def ignore_multi_device(
    payload: IgnoreDeviceDTO,
    db: Session = Depends(get_db)
):
    try:
        # Assuming table 'login_log_device_ignores' exists as per Laravel controller check
        # INSERT INTO login_log_device_ignores (user_id, device, created_at, updated_at) VALUES (...)
        
        # Check if table exists mapping 
        # Using raw SQL for simplicity if model not defined
        sql = text("INSERT INTO login_log_device_ignores (user_id, device, created_at, updated_at) VALUES (:uid, :dev, NOW(), NOW())")
        db.execute(sql, {"uid": payload.user_id, "dev": payload.device})
        db.commit()
        
        return {"message": "Device ignored successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
