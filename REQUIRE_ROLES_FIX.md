# require_roles Fix Documentation

## Problem
Error yang terjadi: `AttributeError: 'function' object has no attribute 'role'`

### Root Cause
`@require_roles([...])` digunakan sebagai decorator langsung, padahal seharusnya digunakan sebagai dependency di dalam `Depends()`.

### Incorrect Usage (Before Fix)
```python
@router.post("/some-endpoint")
@require_roles(["admin", "cfo"])  # ❌ WRONG - Used as decorator
async def some_function(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ❌ This receives function, not User object
):
    pass
```

### Correct Usage (After Fix)
```python
@router.post("/some-endpoint")
async def some_function(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "cfo"]))  # ✅ CORRECT - Used as dependency
):
    pass
```

## Files Fixed

### 1. `app/api/v1/endpoints/epa_cache.py`
- Fixed 5 endpoints that used `@require_roles` as decorator
- Endpoints: `/refresh`, `/cache/status`, `/cache/clear`, `/auto-refresh/start`, `/auto-refresh/stop`

### 2. `app/api/v1/endpoints/epa_ghgrp.py`
- Fixed 2 endpoints that used `@require_roles` as decorator
- Endpoints: `/companies/{company_id}/validation-summary`, `/validation-metrics`

### 3. `app/api/v1/endpoints/enhanced_audit.py`
- Fixed 6 endpoints that used `@require_roles` as decorator
- Endpoints: `/calculations/{calculation_id}/sec-compliance`, `/calculations/{calculation_id}/enhanced-audit`, `/calculations/{calculation_id}/integrity-check`, `/companies/{company_id}/audit-summary`, `/export/audit-trail`, `/calculations/{calculation_id}/forensic-report`

## How require_roles Works

### Function Signature
```python
def require_roles(required_roles: List[str]) -> Callable:
    """
    Creates a FastAPI dependency that checks user roles
    
    Args:
        required_roles: List of roles required to access the endpoint
        
    Returns:
        FastAPI dependency function that validates user roles
    """
```

### Usage Pattern
```python
# Import
from app.core.auth import require_roles

# Use as dependency
@router.get("/admin-only")
async def admin_function(
    current_user: User = Depends(require_roles(["admin"]))
):
    # current_user is now properly a User object with .role attribute
    pass
```

## Why This Fix Works

1. **FastAPI Dependency System**: `Depends()` tells FastAPI to call the function and inject the result
2. **require_roles()** returns a dependency function that:
   - Gets the current user
   - Validates their roles
   - Returns the User object if authorized
   - Raises HTTPException if not authorized
3. **Proper Type**: `current_user` now receives a `User` object, not a function

## Testing
- All syntax errors resolved
- FastAPI app can be created successfully
- All routers can be included without errors
- `require_roles()` returns callable dependency function

## Result
✅ **FIXED**: The `AttributeError: 'function' object has no attribute 'role'` error is now resolved!