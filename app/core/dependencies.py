"""
Core Dependencies
Legacy compatibility layer for dependencies
Redirects to app.api.deps for actual implementations
"""

# Import all dependencies from the main deps module
from app.api.deps import get_current_active_user
from app.api.deps import get_current_superuser
from app.api.deps import get_current_user
from app.api.deps import get_current_user_optional
from app.api.deps import get_db
from app.api.deps import require_access_audit_trails
from app.api.deps import require_admin
from app.api.deps import require_approve_reports
from app.api.deps import require_auditor
from app.api.deps import require_cfo
from app.api.deps import require_finance_team
from app.api.deps import require_general_counsel
from app.api.deps import require_manage_epa_data
from app.api.deps import require_permissions
from app.api.deps import require_read_emissions
from app.api.deps import require_roles
from app.api.deps import require_write_emissions

# Legacy aliases for backward compatibility
get_admin_user = require_admin
