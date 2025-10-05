# Database Migration Workflow - Steering Rules

## CRITICAL: Database Migration Requirements

**EVERY TIME you modify models or implement features that change database schema, you MUST follow this workflow:**

### 🔄 **Mandatory Migration Workflow**

1. **After Model Changes**:

   ```bash
   alembic revision --autogenerate -m "descriptive message about changes"
   ```

2. **Review Migration File**:

   - Check generated migration in `alembic/versions/`
   - Ensure it matches intended changes
   - Fix any issues (SQLite limitations, etc.)

3. **Apply Migration**:

   ```bash
   alembic upgrade head
   ```

4. **Verify with Tests**:
   - Run relevant tests to ensure schema works
   - Fix any test failures due to schema changes

### 📋 **When Migration is Required**

- ✅ Adding new models/tables
- ✅ Adding/removing/modifying fields in existing models
- ✅ Changing field types or constraints
- ✅ Adding/removing indexes
- ✅ Changing relationships between models
- ✅ After completing major tasks (6.1, 6.2, 7.1, etc.)

### 🚨 **Critical Rules**

- **NEVER skip migrations** when models change
- **ONE migration per major feature** for easy rollback
- **Always test after migration** to ensure compatibility
- **Use descriptive migration messages** for tracking
- **Check for SQLite limitations** (no ALTER COLUMN TYPE)

### 📁 **Project Context**

- **Database**: SQLite (development)
- **ORM**: SQLAlchemy with Alembic migrations
- **Models Location**: `app/models/`
- **Migration Location**: `alembic/versions/`
- **Current Schema**: Includes consolidated_emissions, consolidation_audit_trail

### 🎯 **Success Criteria**

- Database schema matches model definitions
- All tests pass after migration
- No schema-related errors in application
- Migration can be rolled back if needed

### ⚠️ **Common Issues to Avoid**

- SQLite doesn't support ALTER COLUMN TYPE - create new migration instead
- Always check if tables already exist before creating
- Use `alembic stamp head` if migration already applied manually
- Test with actual data, not just empty tables

## Implementation Note

This workflow ensures database consistency across development sessions and prevents schema mismatch errors that can break the application.
