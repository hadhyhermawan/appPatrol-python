"""
Permission checking utilities with Super Admin bypass
"""
from fastapi import HTTPException, status, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from typing import List, Optional
from functools import wraps
from jose import jwt, JWTError
from app.core.security import SECRET_KEY, ALGORITHM
from app.models.models import Users
from datetime import datetime, timedelta

SUPER_ADMIN_ROLE = "super admin"

def has_role(db: Session, user_id: int, role_name: str) -> bool:
    """
    Check if user has specific role
    """
    result = db.execute(
        text("""
            SELECT COUNT(*) 
            FROM model_has_roles mhr
            JOIN roles r ON mhr.role_id = r.id
            WHERE mhr.model_id = :user_id 
            AND mhr.model_type = 'App\\\\Models\\\\User'
            AND r.name = :role_name
        """),
        {"user_id": user_id, "role_name": role_name}
    ).scalar()
    
    return result > 0

def is_super_admin(db: Session, user_id: int) -> bool:
    """
    Check if user is Super Admin
    Super Admin is the KING - has access to everything!
    """
    return has_role(db, user_id, SUPER_ADMIN_ROLE)

def get_user_roles(db: Session, user_id: int) -> List[str]:
    """
    Get all roles for a user
    """
    results = db.execute(
        text("""
            SELECT r.name 
            FROM model_has_roles mhr
            JOIN roles r ON mhr.role_id = r.id
            WHERE mhr.model_id = :user_id 
            AND mhr.model_type = 'App\\\\Models\\\\User'
        """),
        {"user_id": user_id}
    ).fetchall()
    
    return [row[0] for row in results]

def get_user_permissions(db: Session, user_id: int) -> List[str]:
    """
    Get all permissions for a user through their roles
    Super Admin automatically gets ALL permissions
    """
    # Check if Super Admin first
    if is_super_admin(db, user_id):
        # Super Admin is KING - return all permissions
        results = db.execute(
            text("SELECT name FROM permissions")
        ).fetchall()
        return [row[0] for row in results]
    
    # For other users, get permissions through roles
    results = db.execute(
        text("""
            SELECT DISTINCT p.name
            FROM model_has_roles mhr
            JOIN role_has_permissions rhp ON mhr.role_id = rhp.role_id
            JOIN permissions p ON rhp.permission_id = p.id
            WHERE mhr.model_id = :user_id 
            AND mhr.model_type = 'App\\\\Models\\\\User'
        """),
        {"user_id": user_id}
    ).fetchall()
    
    return [row[0] for row in results]

def has_permission(db: Session, user_id: int, permission: str) -> bool:
    """
    Check if user has specific permission
    Super Admin ALWAYS returns True - they are the KING!
    """
    # Super Admin bypass - they have ALL permissions
    if is_super_admin(db, user_id):
        return True
    
    # Check specific permission for other users
    result = db.execute(
        text("""
            SELECT COUNT(*)
            FROM model_has_roles mhr
            JOIN role_has_permissions rhp ON mhr.role_id = rhp.role_id
            JOIN permissions p ON rhp.permission_id = p.id
            WHERE mhr.model_id = :user_id 
            AND mhr.model_type = 'App\\\\Models\\\\User'
            AND p.name = :permission
        """),
        {"user_id": user_id, "permission": permission}
    ).scalar()
    
    return result > 0

def has_any_permission(db: Session, user_id: int, permissions: List[str]) -> bool:
    """
    Check if user has ANY of the specified permissions
    Super Admin ALWAYS returns True
    """
    # Super Admin bypass
    if is_super_admin(db, user_id):
        return True
    
    # Check if user has any of the permissions
    for permission in permissions:
        if has_permission(db, user_id, permission):
            return True
    
    return False

def has_all_permissions(db: Session, user_id: int, permissions: List[str]) -> bool:
    """
    Check if user has ALL of the specified permissions
    Super Admin ALWAYS returns True
    """
    # Super Admin bypass
    if is_super_admin(db, user_id):
        return True
    
    # Check if user has all permissions
    for permission in permissions:
        if not has_permission(db, user_id, permission):
            return False
    
    return True

def require_permission(permission: str):
    """
    Decorator to require specific permission
    Super Admin bypasses all permission checks
    
    Usage:
        @require_permission("karyawan.create")
        async def create_karyawan(...):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get db and current_user from kwargs
            db: Session = kwargs.get('db')
            current_user = kwargs.get('current_user')
            
            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Permission check failed: missing dependencies"
                )
            
            # Super Admin bypass - they are the KING!
            if is_super_admin(db, current_user.id):
                return await func(*args, **kwargs)
            
            # Check permission for other users
            if not has_permission(db, current_user.id, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission} required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def require_role(role: str):
    """
    Decorator to require specific role
    Super Admin bypasses all role checks
    
    Usage:
        @require_role("admin departemen")
        async def admin_only_function(...):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get db and current_user from kwargs
            db: Session = kwargs.get('db')
            current_user = kwargs.get('current_user')
            
            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Role check failed: missing dependencies"
                )
            
            # Super Admin bypass - they are the KING!
            if is_super_admin(db, current_user.id):
                return await func(*args, **kwargs)
            
            # Check role for other users
            if not has_role(db, current_user.id, role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: {role} role required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def require_any_role(roles: List[str]):
    """
    Decorator to require ANY of the specified roles
    Super Admin bypasses all role checks
    
    Usage:
        @require_any_role(["super admin", "admin departemen"])
        async def admin_function(...):
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get db and current_user from kwargs
            db: Session = kwargs.get('db')
            current_user = kwargs.get('current_user')
            
            if not db or not current_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Role check failed: missing dependencies"
                )
            
            # Super Admin bypass - they are the KING!
            if is_super_admin(db, current_user.id):
                return await func(*args, **kwargs)
            
            # Check if user has any of the roles
            user_roles = get_user_roles(db, current_user.id)
            if not any(role in user_roles for role in roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: one of {roles} roles required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ============================================================================
# Modern FastAPI Dependency Injection
# ============================================================================

class CurrentUser:
    """Current authenticated user with permissions"""
    def __init__(self, id: int, username: str, roles: List[dict], permissions: List[str], is_super_admin: bool = False):
        self.id = id
        self.username = username
        self.roles = roles
        self.permissions = permissions
        self.is_super_admin = is_super_admin
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        if self.is_super_admin:
            return True
        return permission in self.permissions
    
    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions"""
        if self.is_super_admin:
            return True
        return any(perm in self.permissions for perm in permissions)
    
    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if user has all of the specified permissions"""
        if self.is_super_admin:
            return True
        return all(perm in self.permissions for perm in permissions)


async def get_current_user(
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None)
) -> CurrentUser:
    """
    Dependency to get current authenticated user with their permissions
    
    Usage:
        @router.get("/resource")
        async def get_resource(current_user: CurrentUser = Depends(get_current_user)):
            # current_user has id, username, roles, permissions, is_super_admin
            ...
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Extract token from "Bearer <token>"
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user = db.query(Users).filter(Users.id == int(user_id)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Session Reset Logic: Check if token is older than user's last update
    if "iat" in payload and user.updated_at:
        token_iat = payload["iat"]
        # Convert IAT (timestamp) to naive datetime (UTC) to match user.updated_at which is stored as naive UTC
        token_dt = datetime.utcfromtimestamp(token_iat)
        
        # Buffer of 2 seconds for any tiny clock skews or DB roundtrip time
        if token_dt < (user.updated_at - timedelta(seconds=2)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired (Reset), please login again",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # Get user's roles
    roles_result = db.execute(
        text("""
            SELECT r.id, r.name 
            FROM model_has_roles mhr
            JOIN roles r ON mhr.role_id = r.id
            WHERE mhr.model_id = :user_id 
            AND mhr.model_type = 'App\\\\Models\\\\User'
        """),
        {"user_id": user.id}
    ).fetchall()
    
    roles = [{"id": row[0], "name": row[1]} for row in roles_result]
    
    # Check if super admin (role id = 1 or name = "super admin")
    is_super_admin_user = any(role["id"] == 1 or role["name"] == SUPER_ADMIN_ROLE for role in roles)
    
    # Get user's permissions
    permissions = get_user_permissions(db, user.id)
    
    return CurrentUser(
        id=user.id,
        username=user.username,
        roles=roles,
        permissions=permissions,
        is_super_admin=is_super_admin_user
    )


def require_permission_dependency(permission: str):
    """
    Dependency factory to require a specific permission
    
    Usage:
        @router.post("/resource")
        async def create_resource(
            current_user: CurrentUser = Depends(require_permission_dependency("resource.create"))
        ):
            # User is guaranteed to have the permission
            ...
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required permission: {permission}"
            )
        return current_user
    
    return permission_checker


def require_any_permission_dependency(permissions: List[str]):
    """
    Dependency factory to require any of the specified permissions
    
    Usage:
        @router.get("/resource")
        async def view_resource(
            current_user: CurrentUser = Depends(require_any_permission_dependency(["resource.index", "resource.view"]))
        ):
            # User has at least one of the permissions
            ...
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not current_user.has_any_permission(permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required any of: {', '.join(permissions)}"
            )
        return current_user
    
    return permission_checker


def require_all_permissions_dependency(permissions: List[str]):
    """
    Dependency factory to require all of the specified permissions
    
    Usage:
        @router.post("/resource")
        async def special_action(
            current_user: CurrentUser = Depends(require_all_permissions_dependency(["resource.create", "resource.approve"]))
        ):
            # User has all required permissions
            ...
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not current_user.has_all_permissions(permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required all of: {', '.join(permissions)}"
            )
        return current_user
    
    return permission_checker
