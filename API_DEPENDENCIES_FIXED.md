# API Dependencies - Fixed Missing Files

## 🎯 **Issue Resolved**

Fixed missing dependency files that were being imported in API endpoints but didn't exist in the project structure.

## 📁 **Files Created**

### **1. `app/api/deps.py`** - Main Dependencies Module

- **Database Session**: `get_db()` - SQLAlchemy session management
- **Authentication**: `get_current_user()` - JWT token validation
- **Authorization**: Role-based and permission-based access control
- **Security**: HTTPBearer token extraction and validation

### **2. `app/core/auth.py`** - Authentication & Authorization Utilities

- **Role-based Access Control**: `require_roles()`, `require_admin()`, etc.
- **Permission-based Control**: `require_permissions()`, `AuthorizationChecker`
- **Convenience Functions**: Pre-configured role and permission checks

### **3. `app/core/dependencies.py`** - Legacy Compatibility Layer

- **Backward Compatibility**: Redirects to `app.api.deps` for actual implementations
- **Legacy Aliases**: `get_admin_user = require_admin`

### **4. Enhanced `app/models/user.py`** - User Permission Methods

- **Permission Methods**: `can_read_emissions()`, `can_write_emissions()`, etc.
- **Role Properties**: `is_admin`, `is_cfo`, etc.
- **Permission Dictionary**: `get_permissions()` based on user role

## 🔐 **Authentication Flow**

```python
# 1. Extract JWT token from Authorization header
credentials: HTTPAuthorizationCredentials = Depends(security)

# 2. Decode and validate JWT token
payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])

# 3. Get user from database
user = db.query(User).filter(User.id == user_id).first()

# 4. Check user is active
if not user.is_active: raise HTTPException(401)

# 5. Return authenticated user
return user
```

## 👥 **Role-Based Access Control**

### **User Roles**

- **CFO**: Full emissions access, report approval
- **General Counsel**: Report approval, audit access
- **Finance Team**: Emissions data entry and management
- **Auditor**: Read-only access to audit trails
- **Admin**: Full system access

### **Permission Matrix**

| Permission          | CFO | General Counsel | Finance Team | Auditor | Admin |
| ------------------- | --- | --------------- | ------------ | ------- | ----- |
| Read Emissions      | ✅  | ✅              | ✅           | ✅      | ✅    |
| Write Emissions     | ✅  | ❌              | ✅           | ❌      | ✅    |
| Approve Reports     | ✅  | ✅              | ❌           | ❌      | ✅    |
| Access Audit Trails | ✅  | ❌              | ❌           | ✅      | ✅    |
| Manage EPA Data     | ❌  | ❌              | ❌           | ❌      | ✅    |

## 🛡️ **Security Features**

### **JWT Token Security**

- **Algorithm**: HS256 (HMAC with SHA-256)
- **Expiration**: Configurable access token lifetime
- **Refresh Tokens**: Long-lived refresh capability
- **Token Type Validation**: Access vs refresh token verification

### **Role-Based Protection**

```python
# Require specific role
@router.get("/admin-only")
async def admin_endpoint(user: User = Depends(require_admin())):
    return {"message": "Admin access granted"}

# Require multiple roles
@router.get("/finance-access")
async def finance_endpoint(user: User = Depends(require_roles(["cfo", "finance_team"]))):
    return {"message": "Finance access granted"}
```

### **Permission-Based Protection**

```python
# Require specific permission
@router.post("/emissions")
async def create_emission(user: User = Depends(require_write_emissions())):
    return {"message": "Emission creation allowed"}

# Require multiple permissions
@router.get("/reports")
async def get_reports(user: User = Depends(require_permissions(["read_reports", "read_emissions"]))):
    return {"message": "Report access granted"}
```

## 📡 **Usage Examples**

### **Basic Authentication**

```python
from app.api.deps import get_current_user

@router.get("/protected")
async def protected_endpoint(current_user: User = Depends(get_current_user)):
    return {"user": current_user.email}
```

### **Role-Based Access**

```python
from app.api.deps import require_cfo

@router.post("/approve-calculation")
async def approve_calculation(user: User = Depends(require_cfo())):
    return {"message": "Calculation approved by CFO"}
```

### **Permission-Based Access**

```python
from app.api.deps import require_approve_reports

@router.post("/approve-report")
async def approve_report(user: User = Depends(require_approve_reports())):
    return {"message": "Report approved"}
```

### **Optional Authentication**

```python
from app.api.deps import get_current_user_optional

@router.get("/public-or-private")
async def flexible_endpoint(user: Optional[User] = Depends(get_current_user_optional)):
    if user:
        return {"message": f"Welcome {user.email}"}
    else:
        return {"message": "Welcome anonymous user"}
```

## 🔄 **Compatibility**

### **Legacy Support**

The system maintains backward compatibility with existing imports:

```python
# Old imports still work
from app.core.dependencies import get_current_active_user, get_admin_user

# New recommended imports
from app.api.deps import get_current_active_user, require_admin
```

## ✅ **Verification**

All dependency files have been tested and verified:

- ✅ Import statements work correctly
- ✅ Role-based access control functions properly
- ✅ Permission-based access control works
- ✅ JWT token validation is secure
- ✅ Database session management is efficient
- ✅ Backward compatibility maintained

## 🎯 **Benefits**

- **Security**: Robust JWT-based authentication with role/permission controls
- **Flexibility**: Multiple authorization strategies (role-based, permission-based)
- **Maintainability**: Clean separation of concerns with dedicated dependency modules
- **Compatibility**: Backward compatibility with existing code
- **Performance**: Efficient database session management
- **Scalability**: Easy to extend with new roles and permissions

---

**🎉 API Dependencies: FULLY FUNCTIONAL!**

_All missing dependency files have been created and tested. The authentication and authorization system is now complete and ready for production use._
