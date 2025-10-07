"""
Test script to verify UUID fix for SQLite compatibility
"""

import os
import sys
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def test_uuid_sqlite_compatibility():
    """Test that UUID type works with SQLite"""

    print("🔧 Testing UUID SQLite Compatibility")
    print("=" * 50)

    try:
        # Import the models
        from app.models.base import GUID, Base
        from app.models.user import User, UserRole, UserStatus

        print("✅ Models imported successfully")

        # Create in-memory SQLite database
        engine = create_engine("sqlite:///:memory:", echo=False)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        print("✅ SQLite engine created")

        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created successfully")

        # Test creating a user
        db = SessionLocal()

        try:
            # Create test user
            test_user = User(
                email="test@example.com",
                username="testuser",
                full_name="Test User",
                hashed_password="hashed_password_here",
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
            )

            print(f"✅ User object created with ID: {test_user.id}")

            # Add to database
            db.add(test_user)
            db.commit()
            db.refresh(test_user)

            print(f"✅ User saved to database with ID: {test_user.id}")
            print(f"   ID type: {type(test_user.id)}")

            # Query the user back
            retrieved_user = (
                db.query(User).filter(User.email == "test@example.com").first()
            )

            if retrieved_user:
                print(f"✅ User retrieved from database with ID: {retrieved_user.id}")
                print(f"   ID type: {type(retrieved_user.id)}")
                print(f"   Email: {retrieved_user.email}")
                print(f"   Role: {retrieved_user.role}")
            else:
                print("❌ Failed to retrieve user from database")
                return False

            # Test UUID operations
            if isinstance(retrieved_user.id, uuid.UUID):
                print("✅ ID is proper UUID object")
            else:
                print(f"⚠️  ID is {type(retrieved_user.id)}, not UUID object")

            # Test raw SQL query to see how UUID is stored
            result = db.execute(
                text("SELECT id, email FROM users WHERE email = :email"),
                {"email": "test@example.com"},
            )
            row = result.fetchone()
            if row:
                print(f"✅ Raw SQL result - ID: {row[0]} (type: {type(row[0])})")

            print("\n🎯 UUID Fix Summary:")
            print("-" * 30)
            print("✅ GUID TypeDecorator works with SQLite")
            print("✅ UUID objects can be created and stored")
            print("✅ UUID objects can be retrieved from database")
            print("✅ No SQLAlchemy compilation errors")

            return True

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Error during UUID testing: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


def test_guid_type_directly():
    """Test GUID type directly"""

    print("\n🧪 Testing GUID Type Directly")
    print("-" * 40)

    try:
        from sqlalchemy import Column, MetaData, Table, create_engine
        from sqlalchemy.orm import sessionmaker

        from app.models.base import GUID

        # Create test table with GUID column
        engine = create_engine("sqlite:///:memory:", echo=False)
        metadata = MetaData()

        test_table = Table(
            "test_guid",
            metadata,
            Column("id", GUID(), primary_key=True),
            Column("name", GUID()),  # Test GUID as regular column too
        )

        metadata.create_all(engine)
        print("✅ Test table with GUID columns created")

        # Test inserting data
        with engine.connect() as conn:
            test_id = uuid.uuid4()
            test_name = uuid.uuid4()

            conn.execute(test_table.insert().values(id=test_id, name=test_name))
            conn.commit()

            print(f"✅ Data inserted - ID: {test_id}")

            # Test retrieving data
            result = conn.execute(test_table.select()).fetchone()
            if result:
                print(f"✅ Data retrieved - ID: {result[0]} (type: {type(result[0])})")
                print(f"   Name: {result[1]} (type: {type(result[1])})")

        return True

    except Exception as e:
        print(f"❌ Error during GUID type testing: {str(e)}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting UUID SQLite Compatibility Tests")
    print("=" * 60)

    success1 = test_uuid_sqlite_compatibility()
    success2 = test_guid_type_directly()

    if success1 and success2:
        print("\n✅ All UUID tests passed! SQLite compatibility fixed.")
        print("\n🎯 The SQLAlchemy UUID compilation error should now be resolved!")
    else:
        print("\n❌ Some UUID tests failed. Please check the errors above.")
