"""
Core Dependencies
Legacy compatibility layer for dependencies
Redirects to app.api.deps for actual implementations
"""

# Import all dependencies from the main deps module
from app.api.deps import (
    get_db,
    get_current_user,
    get_current_active_user,
    get_current_superuser,
    get_current_user_optional,
    require_roles,
    require_permissions,
    require_admin,
    require_cfo,
    require_general_counsel,
    require_finance_team,
    require_auditor,
    require_read_emissions,
    require_write_emissions,
    require_approve_reports,
    require_manage_epa_data,
    require_access_audit_trails,
)

# Legacy aliases for backward compatibility
get_admin_user = require_admin
