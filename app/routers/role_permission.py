from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.core.permissions import require_role, is_super_admin
from app.schemas.role_permission import (
    RoleCreate, RoleUpdate, RoleResponse,
    PermissionCreate, PermissionUpdate, PermissionResponse,
    PermissionGroupCreate, PermissionGroupUpdate, PermissionGroupResponse,
    AssignPermissionRequest, AssignPermissionGroupRequest, RemovePermissionRequest,
    AssignRoleToUserRequest, RemoveRoleFromUserRequest,
    RolePermissionsResponse, UserRolesResponse, PermissionMatrixResponse
)
from typing import List
from datetime import datetime

# Temporary: Simple user object for dependency injection
# TODO: Replace with proper JWT authentication
class CurrentUser:
    def __init__(self, id: int):
        self.id = id

def get_current_user() -> CurrentUser:
    """Temporary function - returns Super Admin user for testing"""
    # TODO: Implement proper JWT token validation
    return CurrentUser(id=1)  # Super Admin


router = APIRouter(
    prefix="/api/role-permission",
    tags=["Role & Permission Management"]
)

# ==================== ROLES ====================

@router.get("/roles", response_model=List[RoleResponse])
async def get_all_roles(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all roles with permission count (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can access role management"
        )
    
    results = db.execute(text("""
        SELECT 
            r.id,
            r.name,
            r.guard_name,
            r.created_at,
            r.updated_at,
            COUNT(rhp.permission_id) as permission_count
        FROM roles r
        LEFT JOIN role_has_permissions rhp ON r.id = rhp.role_id
        GROUP BY r.id, r.name, r.guard_name, r.created_at, r.updated_at
        ORDER BY r.id
    """)).fetchall()
    
    return [
        {
            "id": row[0],
            "name": row[1],
            "guard_name": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "permission_count": row[5] or 0
        }
        for row in results
    ]

@router.get("/roles/{role_id}", response_model=RolePermissionsResponse)
async def get_role_details(
    role_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get role details with all permissions (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can access role management"
        )
    
    # Get role
    role_result = db.execute(
        text("SELECT id, name, guard_name, created_at, updated_at FROM roles WHERE id = :role_id"),
        {"role_id": role_id}
    ).fetchone()
    
    if not role_result:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Get permissions
    perm_results = db.execute(text("""
        SELECT 
            p.id,
            p.name,
            p.guard_name,
            p.id_permission_group,
            p.created_at,
            p.updated_at,
            pg.name as group_name
        FROM role_has_permissions rhp
        JOIN permissions p ON rhp.permission_id = p.id
        JOIN permission_groups pg ON p.id_permission_group = pg.id
        WHERE rhp.role_id = :role_id
        ORDER BY pg.name, p.name
    """), {"role_id": role_id}).fetchall()
    
    # Count permissions
    perm_count = len(perm_results)
    
    return {
        "role": {
            "id": role_result[0],
            "name": role_result[1],
            "guard_name": role_result[2],
            "created_at": role_result[3],
            "updated_at": role_result[4],
            "permission_count": perm_count
        },
        "permissions": [
            {
                "id": row[0],
                "name": row[1],
                "guard_name": row[2],
                "id_permission_group": row[3],
                "created_at": row[4],
                "updated_at": row[5],
                "group_name": row[6]
            }
            for row in perm_results
        ]
    }

@router.post("/roles", response_model=RoleResponse)
async def create_role(
    role: RoleCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new role (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can create roles"
        )
    
    # Check if role exists
    existing = db.execute(
        text("SELECT id FROM roles WHERE name = :name"),
        {"name": role.name}
    ).fetchone()
    
    if existing:
        raise HTTPException(status_code=400, detail="Role already exists")
    
    # Create role
    db.execute(text("""
        INSERT INTO roles (name, guard_name, created_at, updated_at)
        VALUES (:name, :guard_name, NOW(), NOW())
    """), {"name": role.name, "guard_name": role.guard_name})
    db.commit()
    
    # Get created role
    result = db.execute(
        text("SELECT id, name, guard_name, created_at, updated_at FROM roles WHERE name = :name"),
        {"name": role.name}
    ).fetchone()
    
    return {
        "id": result[0],
        "name": result[1],
        "guard_name": result[2],
        "created_at": result[3],
        "updated_at": result[4],
        "permission_count": 0
    }

@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role: RoleUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update role (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can update roles"
        )
    
    # Check if role exists
    existing = db.execute(
        text("SELECT id FROM roles WHERE id = :role_id"),
        {"role_id": role_id}
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Update role
    if role.name:
        db.execute(text("""
            UPDATE roles 
            SET name = :name, updated_at = NOW()
            WHERE id = :role_id
        """), {"name": role.name, "role_id": role_id})
        db.commit()
    
    # Get updated role
    result = db.execute(text("""
        SELECT 
            r.id, r.name, r.guard_name, r.created_at, r.updated_at,
            COUNT(rhp.permission_id) as permission_count
        FROM roles r
        LEFT JOIN role_has_permissions rhp ON r.id = rhp.role_id
        WHERE r.id = :role_id
        GROUP BY r.id, r.name, r.guard_name, r.created_at, r.updated_at
    """), {"role_id": role_id}).fetchone()
    
    return {
        "id": result[0],
        "name": result[1],
        "guard_name": result[2],
        "created_at": result[3],
        "updated_at": result[4],
        "permission_count": result[5] or 0
    }

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Delete role (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can delete roles"
        )
    
    # Prevent deleting Super Admin role
    if role_id == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete Super Admin role"
        )
    
    # Delete role (cascade will handle role_has_permissions and model_has_roles)
    db.execute(text("DELETE FROM role_has_permissions WHERE role_id = :role_id"), {"role_id": role_id})
    db.execute(text("DELETE FROM model_has_roles WHERE role_id = :role_id"), {"role_id": role_id})
    db.execute(text("DELETE FROM roles WHERE id = :role_id"), {"role_id": role_id})
    db.commit()
    
    return {"message": "Role deleted successfully"}

# ==================== PERMISSION GROUPS ====================

@router.get("/permission-groups", response_model=List[PermissionGroupResponse])
async def get_all_permission_groups(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all permission groups with permission count (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can access permission management"
        )
    
    results = db.execute(text("""
        SELECT 
            pg.id,
            pg.name,
            pg.created_at,
            pg.updated_at,
            COUNT(p.id) as permission_count
        FROM permission_groups pg
        LEFT JOIN permissions p ON pg.id = p.id_permission_group
        GROUP BY pg.id, pg.name, pg.created_at, pg.updated_at
        ORDER BY pg.id
    """)).fetchall()
    
    return [
        {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "permission_count": row[4] or 0
        }
        for row in results
    ]

@router.post("/permission-groups", response_model=PermissionGroupResponse)
async def create_permission_group(
    group: PermissionGroupCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new permission group (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can create permission groups"
        )
    
    # Create group
    db.execute(text("""
        INSERT INTO permission_groups (name, created_at, updated_at)
        VALUES (:name, NOW(), NOW())
    """), {"name": group.name})
    db.commit()
    
    # Get created group
    result = db.execute(
        text("SELECT id, name, created_at, updated_at FROM permission_groups WHERE name = :name"),
        {"name": group.name}
    ).fetchone()
    
    return {
        "id": result[0],
        "name": result[1],
        "created_at": result[2],
        "updated_at": result[3],
        "permission_count": 0
    }

# ==================== PERMISSIONS ====================

@router.get("/permissions", response_model=List[PermissionResponse])
async def get_all_permissions(
    group_id: int = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all permissions, optionally filtered by group (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can access permission management"
        )
    
    query = """
        SELECT 
            p.id,
            p.name,
            p.guard_name,
            p.id_permission_group,
            p.created_at,
            p.updated_at,
            pg.name as group_name
        FROM permissions p
        JOIN permission_groups pg ON p.id_permission_group = pg.id
    """
    
    params = {}
    if group_id:
        query += " WHERE p.id_permission_group = :group_id"
        params["group_id"] = group_id
    
    query += " ORDER BY pg.name, p.name"
    
    results = db.execute(text(query), params).fetchall()
    
    return [
        {
            "id": row[0],
            "name": row[1],
            "guard_name": row[2],
            "id_permission_group": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "group_name": row[6]
        }
        for row in results
    ]

@router.post("/permissions", response_model=PermissionResponse)
async def create_permission(
    permission: PermissionCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create new permission (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can create permissions"
        )
    
    # Check if permission exists
    existing = db.execute(
        text("SELECT id FROM permissions WHERE name = :name"),
        {"name": permission.name}
    ).fetchone()
    
    if existing:
        raise HTTPException(status_code=400, detail="Permission already exists")
    
    # Create permission
    db.execute(text("""
        INSERT INTO permissions (name, guard_name, id_permission_group, created_at, updated_at)
        VALUES (:name, :guard_name, :group_id, NOW(), NOW())
    """), {
        "name": permission.name,
        "guard_name": permission.guard_name,
        "group_id": permission.id_permission_group
    })
    db.commit()
    
    # Get created permission
    result = db.execute(text("""
        SELECT 
            p.id, p.name, p.guard_name, p.id_permission_group,
            p.created_at, p.updated_at, pg.name as group_name
        FROM permissions p
        JOIN permission_groups pg ON p.id_permission_group = pg.id
        WHERE p.name = :name
    """), {"name": permission.name}).fetchone()
    
    return {
        "id": result[0],
        "name": result[1],
        "guard_name": result[2],
        "id_permission_group": result[3],
        "created_at": result[4],
        "updated_at": result[5],
        "group_name": result[6]
    }

# ==================== ASSIGN/REMOVE PERMISSIONS ====================

@router.post("/assign-permissions")
async def assign_permissions_to_role(
    request: AssignPermissionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Assign permissions to role (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can assign permissions"
        )
    
    # Assign permissions
    for perm_id in request.permission_ids:
        db.execute(text("""
            INSERT IGNORE INTO role_has_permissions (permission_id, role_id)
            VALUES (:perm_id, :role_id)
        """), {"perm_id": perm_id, "role_id": request.role_id})
    
    db.commit()
    
    return {"message": f"Assigned {len(request.permission_ids)} permissions to role"}

@router.post("/assign-permission-group")
async def assign_permission_group_to_role(
    request: AssignPermissionGroupRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Assign all permissions from a group to role (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can assign permissions"
        )
    
    # Assign all permissions from group
    db.execute(text("""
        INSERT IGNORE INTO role_has_permissions (permission_id, role_id)
        SELECT id, :role_id
        FROM permissions
        WHERE id_permission_group = :group_id
    """), {"role_id": request.role_id, "group_id": request.group_id})
    
    db.commit()
    
    # Count assigned
    count = db.execute(
        text("SELECT COUNT(*) FROM permissions WHERE id_permission_group = :group_id"),
        {"group_id": request.group_id}
    ).scalar()
    
    return {"message": f"Assigned {count} permissions from group to role"}

@router.post("/remove-permissions")
async def remove_permissions_from_role(
    request: RemovePermissionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Remove permissions from role (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can remove permissions"
        )
    
    # Remove permissions
    for perm_id in request.permission_ids:
        db.execute(text("""
            DELETE FROM role_has_permissions
            WHERE permission_id = :perm_id AND role_id = :role_id
        """), {"perm_id": perm_id, "role_id": request.role_id})
    
    db.commit()
    
    return {"message": f"Removed {len(request.permission_ids)} permissions from role"}

# ==================== USER ROLES ====================

@router.post("/assign-roles-to-user")
async def assign_roles_to_user(
    request: AssignRoleToUserRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Assign roles to user (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can assign roles to users"
        )
    
    # Assign roles
    for role_id in request.role_ids:
        db.execute(text("""
            INSERT IGNORE INTO model_has_roles (role_id, model_type, model_id)
            VALUES (:role_id, 'App\\\\Models\\\\User', :user_id)
        """), {"role_id": role_id, "user_id": request.user_id})
    
    db.commit()
    
    return {"message": f"Assigned {len(request.role_ids)} roles to user"}

@router.get("/users/{user_id}/roles", response_model=UserRolesResponse)
async def get_user_roles(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get user roles and permissions (Super Admin only)"""
    if not is_super_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Admin can view user roles"
        )
    
    # Get user info
    user = db.execute(
        text("SELECT id, username, name FROM users WHERE id = :user_id"),
        {"user_id": user_id}
    ).fetchone()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get roles
    roles = db.execute(text("""
        SELECT r.id, r.name, r.guard_name, r.created_at, r.updated_at,
               COUNT(rhp.permission_id) as permission_count
        FROM model_has_roles mhr
        JOIN roles r ON mhr.role_id = r.id
        LEFT JOIN role_has_permissions rhp ON r.id = rhp.role_id
        WHERE mhr.model_id = :user_id AND mhr.model_type = 'App\\\\Models\\\\User'
        GROUP BY r.id, r.name, r.guard_name, r.created_at, r.updated_at
    """), {"user_id": user_id}).fetchall()
    
    # Get permissions
    permissions = db.execute(text("""
        SELECT DISTINCT p.name
        FROM model_has_roles mhr
        JOIN role_has_permissions rhp ON mhr.role_id = rhp.role_id
        JOIN permissions p ON rhp.permission_id = p.id
        WHERE mhr.model_id = :user_id AND mhr.model_type = 'App\\\\Models\\\\User'
        ORDER BY p.name
    """), {"user_id": user_id}).fetchall()
    
    return {
        "user_id": user[0],
        "username": user[1],
        "name": user[2],
        "roles": [
            {
                "id": row[0],
                "name": row[1],
                "guard_name": row[2],
                "created_at": row[3],
                "updated_at": row[4],
                "permission_count": row[5] or 0
            }
            for row in roles
        ],
        "permissions": [row[0] for row in permissions]
    }
