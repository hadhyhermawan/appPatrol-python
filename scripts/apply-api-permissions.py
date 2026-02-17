#!/usr/bin/env python3
"""
Bulk apply API-level permissions to all endpoints in FastAPI routers
Adds CurrentUser dependency and permission checks to CRUD operations
"""

import os
import re
from typing import List, Tuple

# Mapping of router files to their resource permissions
ROUTER_PERMISSIONS = {
    "master.py": [
        # Format: (endpoint_pattern, http_method, permission)
        # Departemen - already done, but included for completeness
        (r'@router\.get\("/departemen"', "GET", "departemen.index"),
        (r'@router\.post\("/departemen"', "POST", "departemen.create"),
        (r'@router\.put\("/departemen/\{kode_dept\}"', "PUT", "departemen.update"),
        (r'@router\.delete\("/departemen/\{kode_dept\}"', "DELETE", "departemen.delete"),
        
        # Jabatan
        (r'@router\.get\("/jabatan"', "GET", "jabatan.index"),
        (r'@router\.post\("/jabatan"', "POST", "jabatan.create"),
        (r'@router\.put\("/jabatan/\{kode_jabatan\}"', "PUT", "jabatan.update"),
        (r'@router\.delete\("/jabatan/\{kode_jabatan\}"', "DELETE", "jabatan.delete"),
        
        # Cabang
        (r'@router\.get\("/cabang"', "GET", "cabang.index"),
        (r'@router\.post\("/cabang"', "POST", "cabang.create"),
        (r'@router\.put\("/cabang/\{kode_cabang\}"', "PUT", "cabang.update"),
        (r'@router\.delete\("/cabang/\{kode_cabang\}"', "DELETE", "cabang.delete"),
        
        # Patrol Points
        (r'@router\.get\("/patrol-points"', "GET", "patrolpoint.index"),
        (r'@router\.post\("/patrol-points"', "POST", "patrolpoint.create"),
        (r'@router\.put\("/patrol-points/\{id\}"', "PUT", "patrolpoint.update"),
        (r'@router\.delete\("/patrol-points/\{id\}"', "DELETE", "patrolpoint.delete"),
        
        # Cuti
        (r'@router\.get\("/cuti"', "GET", "cuti.index"),
        (r'@router\.post\("/cuti"', "POST", "cuti.create"),
        (r'@router\.put\("/cuti/\{kode_cuti\}"', "PUT", "cuti.update"),
        (r'@router\.delete\("/cuti/\{kode_cuti\}"', "DELETE", "cuti.delete"),
        
        # Jam Kerja
        (r'@router\.get\("/jamkerja"', "GET", "jamkerja.index"),
        (r'@router\.post\("/jamkerja"', "POST", "jamkerja.create"),
        (r'@router\.put\("/jamkerja/\{kode\}"', "PUT", "jamkerja.update"),
        (r'@router\.delete\("/jamkerja/\{kode\}"', "DELETE", "jamkerja.delete"),
        
        # Patrol Schedules (Jadwal)
        (r'@router\.get\("/patrol-schedules"', "GET", "jadwal.index"),
        (r'@router\.post\("/patrol-schedules"', "POST", "jadwal.create"),
        (r'@router\.put\("/patrol-schedules/\{id\}"', "PUT", "jadwal.update"),
        (r'@router\.delete\("/patrol-schedules/\{id\}"', "DELETE", "jadwal.delete"),
        
        # Karyawan
        (r'@router\.get\("/karyawan"', "GET", "karyawan.index"),
        (r'@router\.post\("/karyawan"', "POST", "karyawan.create"),
        (r'@router\.put\("/karyawan/\{nik\}"', "PUT", "karyawan.update"),
        (r'@router\.delete\("/karyawan/\{nik\}"', "DELETE", "karyawan.delete"),
    ],
    
    "utilities.py": [
        # Users
        (r'@router\.get\("/users"', "GET", "users.index"),
        (r'@router\.post\("/users"', "POST", "users.create"),
        (r'@router\.put\("/users/\{user_id\}"', "PUT", "users.update"),
        (r'@router\.delete\("/users/\{user_id\}"', "DELETE", "users.delete"),
        
        # Roles
        (r'@router\.get\("/roles"', "GET", "roles.index"),
        (r'@router\.post\("/roles"', "POST", "roles.create"),
        (r'@router\.put\("/roles/\{role_id\}"', "PUT", "roles.update"),
        (r'@router\.delete\("/roles/\{role_id\}"', "DELETE", "roles.delete"),
        
        # Permissions
        (r'@router\.get\("/permissions"', "GET", "permissions.index"),
        (r'@router\.post\("/permissions"', "POST", "permissions.create"),
        (r'@router\.put\("/permissions/\{permission_id\}"', "PUT", "permissions.update"),
        (r'@router\.delete\("/permissions/\{permission_id\}"', "DELETE", "permissions.delete"),
        
        # Permission Groups
        (r'@router\.get\("/permission-groups"', "GET", "permissiongroups.index"),
        (r'@router\.post\("/permission-groups"', "POST", "permissiongroups.create"),
        (r'@router\.put\("/permission-groups/\{group_id\}"', "PUT", "permissiongroups.update"),
        (r'@router\.delete\("/permission-groups/\{group_id\}"', "DELETE", "permissiongroups.delete"),
        
        # Logs
        (r'@router\.get\("/logs"', "GET", "logs.index"),
        (r'@router\.delete\("/logs/\{log_id\}"', "DELETE", "logs.delete"),
        
        # Multi Device
        (r'@router\.get\("/multi-device"', "GET", "multidevice.index"),
        (r'@router\.delete\("/multi-device/\{device_id\}"', "DELETE", "multidevice.delete"),
    ],
}

BASE_DIR = "/var/www/appPatrol-python/app/routers"

def has_permission_import(content: str) -> bool:
    """Check if file already imports permission utilities"""
    return "from app.core.permissions import" in content

def add_permission_import(content: str) -> str:
    """Add permission imports if not exists"""
    if has_permission_import(content):
        return content
    
    # Find the last import line
    import_lines = []
    other_lines = []
    in_imports = True
    
    for line in content.split('\n'):
        if in_imports and (line.startswith('from ') or line.startswith('import ')):
            import_lines.append(line)
        else:
            if line.strip() and not line.startswith('#'):
                in_imports = False
            other_lines.append(line)
    
    # Add permission import
    import_lines.append("from app.core.permissions import CurrentUser, get_current_user, require_permission_dependency")
    
    return '\n'.join(import_lines) + '\n' + '\n'.join(other_lines)

def find_function_signature(content: str, decorator_pattern: str) -> Tuple[int, int, str]:
    """
    Find the function signature after a decorator
    Returns: (start_line, end_line, function_signature)
    """
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if re.search(decorator_pattern, line):
            # Found decorator, now find function signature
            j = i + 1
            while j < len(lines):
                if lines[j].strip().startswith('async def ') or lines[j].strip().startswith('def '):
                    # Found function start
                    # Find where parameters end (look for ):)
                    func_lines = [lines[j]]
                    k = j + 1
                    while k < len(lines) and '):' not in lines[k-1]:
                        func_lines.append(lines[k])
                        k += 1
                    
                    return (i, k, '\n'.join(func_lines))
                j += 1
    
    return (-1, -1, "")

def has_current_user_param(func_signature: str) -> bool:
    """Check if function already has current_user parameter"""
    return "current_user" in func_signature

def add_permission_to_endpoint(content: str, decorator_pattern: str, permission: str) -> str:
    """Add permission dependency to an endpoint"""
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        if re.search(decorator_pattern, line):
            # Found decorator
            # Find function definition
            j = i + 1
            while j < len(lines) and not (lines[j].strip().startswith('async def ') or lines[j].strip().startswith('def ')):
                j += 1
            
            if j >= len(lines):
                continue
            
            # Check if already has current_user
            func_start = j
            func_end = j
            
            # Find end of function signature
            while func_end < len(lines) and '):' not in lines[func_end]:
                func_end += 1
            
            func_signature = '\n'.join(lines[func_start:func_end+1])
            
            if has_current_user_param(func_signature):
                # Already protected
                continue
            
            # Find where to insert current_user parameter
            # Look for the line with db: Session = Depends(get_db)
            db_line_idx = -1
            for k in range(func_start, func_end + 1):
                if 'db: Session = Depends(get_db)' in lines[k]:
                    db_line_idx = k
                    break
            
            if db_line_idx == -1:
                # No db parameter, add current_user before ):
                for k in range(func_start, func_end + 1):
                    if '):' in lines[k]:
                        # Insert before ):
                        indent = len(lines[k]) - len(lines[k].lstrip())
                        new_param = ' ' * indent + f'current_user: CurrentUser = Depends(require_permission_dependency("{permission}")),'
                        lines.insert(k, new_param)
                        break
            else:
                # Insert current_user before db parameter
                indent = len(lines[db_line_idx]) - len(lines[db_line_idx].lstrip())
                new_param = ' ' * indent + f'current_user: CurrentUser = Depends(require_permission_dependency("{permission}")),'
                lines.insert(db_line_idx, new_param)
            
            return '\n'.join(lines)
    
    return content

def apply_permissions_to_file(file_path: str, permissions: List[Tuple[str, str, str]]) -> int:
    """Apply permissions to all endpoints in a file"""
    
    if not os.path.exists(file_path):
        print(f"⚠️  File not found: {file_path}")
        return 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Step 1: Add imports
    content = add_permission_import(content)
    
    # Step 2: Apply permissions to each endpoint
    applied_count = 0
    for decorator_pattern, method, permission in permissions:
        old_content = content
        content = add_permission_to_endpoint(content, decorator_pattern, permission)
        if content != old_content:
            applied_count += 1
            print(f"   ✅ {method:6} {permission}")
    
    # Only write if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return applied_count
    
    return 0

def main():
    print("🛡️  Starting bulk API permission application...\n")
    
    total_applied = 0
    total_files = 0
    
    for router_file, permissions in ROUTER_PERMISSIONS.items():
        file_path = os.path.join(BASE_DIR, router_file)
        print(f"📄 Processing {router_file}...")
        
        applied = apply_permissions_to_file(file_path, permissions)
        
        if applied > 0:
            total_applied += applied
            total_files += 1
            print(f"   ✅ Applied {applied} permissions\n")
        else:
            print(f"   ⏭️  No changes needed\n")
    
    print(f"✅ Summary:")
    print(f"   Files Modified: {total_files}")
    print(f"   Permissions Applied: {total_applied}")
    print(f"\n🎉 API-Level Permissions Applied!")
    print(f"\n⚠️  IMPORTANT: Restart backend with: pm2 restart patrol-backend")

if __name__ == "__main__":
    main()
