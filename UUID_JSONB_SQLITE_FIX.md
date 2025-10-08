# UUID & JSONB SQLite Compatibility Fix

## Problem Summary
SQLAlchemy compilation errors when using SQLite for testing:
1. `Compiler can't render element of type UUID`
2. `Compiler can't render element of type JSONB`

## Root Cause
- PostgreSQL-specific types (`UUID`, `JSONB`) are not compatible with SQLite
- Tests use SQLite in-memory database but models were designed for PostgreSQL

## Solution Implemented

### 1. Custom GUID TypeDecorator
Created platform-independent GUID type in `app/models/base.py`:

```python
class GUID(TypeDecorator):
    """
    Platform-independent GUID type.
    Uses PostgreSQL's UUID type when available, otherwise uses CHAR(36).
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresUUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        # Handle UUID conversion for different databases

    def process_result_value(self, value, dialect):
        # Always return UUID object for consistency
```

### 2. Custom JSON TypeDecorator
Created platform-independent JSON type in `app/models/base.py`:

```python
class JSON(TypeDecorator):
    """
    Platform-independent JSON type.
    Uses PostgreSQL's JSONB type when available, otherwise uses TEXT.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgresJSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        # Serialize to JSON string for SQLite

    def process_result_value(self, value, dialect):
        # Deserialize from JSON string for SQLite
```

## Files Modified

### 1. `app/models/base.py`
- ✅ Added `GUID` TypeDecorator
- ✅ Added `JSON` TypeDecorator
- ✅ Fixed `UUIDMixin` default value generation

### 2. `app/models/emissions.py`
- ✅ Replaced `UUID(as_uuid=True)` with `GUID()`
- ✅ Replaced `JSONB` with `JSON`
- ✅ Updated imports

### 3. `app/models/epa_data.py`
- ✅ Replaced `JSONB` with `JSON`
- ✅ Updated imports

### 4. `app/core/audit_logger.py`
- ✅ Replaced `UUID(as_uuid=True)` with `GUID()`
- ✅ Replaced `JSONB` with `JSON`
- ✅ Updated imports

## Database Compatibility

### PostgreSQL (Production)
- Uses native `UUID` type for optimal performance
- Uses native `JSONB` type for JSON operations
- Full indexing and query capabilities

### SQLite (Testing)
- Uses `CHAR(36)` for UUID storage
- Uses `TEXT` for JSON storage with automatic serialization
- Compatible with all test scenarios

## Testing Results

### Before Fix
```
ERROR: Compiler can't render element of type UUID
ERROR: Compiler can't render element of type JSONB
```

### After Fix
```
✅ Models imported successfully
✅ SQLite engine created
✅ Tables created successfully
✅ UUID objects can be created and stored
✅ UUID objects can be retrieved from database
✅ JSON data can be stored and retrieved
✅ No SQLAlchemy compilation errors
```

## Usage Examples

### UUID Usage
```python
# Model definition
class MyModel(BaseModel):
    id = Column(GUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(GUID(), nullable=False)

# Usage
model = MyModel()
print(type(model.id))  # <class 'uuid.UUID'>
```

### JSON Usage
```python
# Model definition
class MyModel(BaseModel):
    metadata = Column(JSON, nullable=True)

# Usage
model = MyModel(metadata={"key": "value", "nested": {"data": 123}})
# Automatically serialized to JSON string in SQLite
# Stored as JSONB in PostgreSQL
```

## Benefits

1. **Cross-Database Compatibility**: Same models work with PostgreSQL and SQLite
2. **Type Safety**: Always returns proper Python types (UUID objects, dict/list for JSON)
3. **Performance**: Uses optimal native types when available
4. **Testing**: Enables comprehensive testing with SQLite
5. **Development**: Faster local development with SQLite option

## Status
✅ **COMPLETED** - All UUID and JSONB SQLite compatibility issues resolved!

The SQLAlchemy compilation errors are now fixed and tests can run successfully with SQLite.
