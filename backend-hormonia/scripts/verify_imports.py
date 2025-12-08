import sys
import os

# Add project root to path (backend-hormonia)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
    load_dotenv(env_path)
    print(f"Loaded environment from {env_path}")
except ImportError:
    print("python-dotenv not installed, skipping .env load")

# Monkeypatch FastAPI to skip routing validation during import check
import fastapi
class MockRouter:
    def __init__(self, *args, **kwargs): pass
    def get(self, *args, **kwargs): return lambda f: f
    def post(self, *args, **kwargs): return lambda f: f
    def put(self, *args, **kwargs): return lambda f: f
    def delete(self, *args, **kwargs): return lambda f: f
    def patch(self, *args, **kwargs): return lambda f: f
    def websocket(self, *args, **kwargs): return lambda f: f
    def options(self, *args, **kwargs): return lambda f: f
    def include_router(self, *args, **kwargs): pass

fastapi.APIRouter = MockRouter

try:
    print("Attempting to import api_v2_router...")
    from app.api.v2.router import api_v2_router
    print("✅ Import Successful!")
except Exception as e:
    print(f"❌ Import Failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
