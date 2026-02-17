from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Role Schemas
class RoleBase(BaseModel):
    name: str
    guard_name: str = "web"

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None

class RoleResponse(RoleBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    permission_count: int = 0
    
    class Config:
        from_attributes = True

# Permission Schemas
class PermissionBase(BaseModel):
    name: str
    guard_name: str = "web"
    id_permission_group: int

class PermissionCreate(PermissionBase):
    pass

class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    id_permission_group: Optional[int] = None

class PermissionResponse(PermissionBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    group_name: Optional[str] = None
    
    class Config:
        from_attributes = True

# Permission Group Schemas
class PermissionGroupBase(BaseModel):
    name: str

class PermissionGroupCreate(PermissionGroupBase):
    pass

class PermissionGroupUpdate(BaseModel):
    name: Optional[str] = None

class PermissionGroupResponse(PermissionGroupBase):
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    permission_count: int = 0
    
    class Config:
        from_attributes = True

# Role Permission Assignment
class AssignPermissionRequest(BaseModel):
    role_id: int
    permission_ids: List[int]

class AssignPermissionGroupRequest(BaseModel):
    role_id: int
    group_id: int

class RemovePermissionRequest(BaseModel):
    role_id: int
    permission_ids: List[int]

class AssignRoleToUserRequest(BaseModel):
    user_id: int
    role_ids: List[int]

class RemoveRoleFromUserRequest(BaseModel):
    user_id: int
    role_ids: List[int]

# Response Schemas
class RolePermissionsResponse(BaseModel):
    role: RoleResponse
    permissions: List[PermissionResponse]

class UserRolesResponse(BaseModel):
    user_id: int
    username: str
    name: str
    roles: List[RoleResponse]
    permissions: List[str]

class PermissionMatrixResponse(BaseModel):
    groups: List[PermissionGroupResponse]
    roles: List[RoleResponse]
    matrix: dict  # {group_id: {role_id: [permission_ids]}}
