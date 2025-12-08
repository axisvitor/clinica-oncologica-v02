"""
Test script to verify monthly_quiz_operations package imports work correctly.
"""

def test_imports():
    """Test that all modules can be imported successfully."""
    try:
        # Test main package import
        from app.api.v2.routers.monthly_quiz_operations import router
        print("✓ Main package import successful")

        # Test sub-module imports
        from app.api.v2.routers.monthly_quiz_operations import crud
        print("✓ CRUD module import successful")

        from app.api.v2.routers.monthly_quiz_operations import scheduling
        print("✓ Scheduling module import successful")

        from app.api.v2.routers.monthly_quiz_operations import public
        print("✓ Public module import successful")

        from app.api.v2.routers.monthly_quiz_operations import health
        print("✓ Health module import successful")

        # Test shared imports
        from app.api.v2.routers.monthly_quiz_operations._shared import logger, PUBLIC_PATIENT_ID
        print("✓ Shared module import successful")

        # Verify router type
        from fastapi import APIRouter
        assert isinstance(router, APIRouter), "Router is not an APIRouter instance"
        print("✓ Router type verification successful")

        # Count routes in main router
        route_count = len([r for r in router.routes])
        print(f"✓ Router has {route_count} routes registered")

        print("\n✅ All imports successful!")
        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    test_imports()
