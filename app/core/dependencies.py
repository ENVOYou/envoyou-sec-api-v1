"""
Core Dependencies
Legacy compatibility layer for dependencies
Redirects to app.api.deps for actual implementations
"""

# Import all dependencies from the main deps module
from app.api.deps import (
    get_current_active_user,
    get_current_superuser,
    get_current_user,
    get_current_user_optional,
    get_db,
    require_access_audit_trails,
    require_admin,
    require_approve_reports,
    require_auditor,
    require_cfo,
    require_finance_team,
    require_general_counsel,
    require_manage_epa_data,
    require_permissions,
    require_read_emissions,
    require_roles,
    require_write_emissions,
)

# Legacy aliases for backward compatibility
get_admin_user = require_admin
