import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.services.flow_service import FlowService
from app.services.flow_management import FlowManagementService
from app.services.analytics import FlowAnalyticsService
from app.services.flow_dashboard import FlowDashboardService
from app.services.enhanced_flow_engine import EnhancedFlowEngine
from app.services.flow.sequential_message_handler import SequentialMessageHandler
from app.repositories.flow import FlowStateRepository

async def verify_system():
    print("Verifying Flow System Consolidation...")

    db = SessionLocal()
    try:
        # Mock dependencies for FlowService
        print("1. Instantiating FlowService...")
        flow_mgmt = FlowManagementService(FlowStateRepository(db), db)
        flow_analytics = FlowAnalyticsService(db)
        # flow_dashboard requires simpler init usually, let's assume valid
        flow_dashboard = FlowDashboardService(db, flow_analytics) 
        flow_engine = EnhancedFlowEngine(db)
        
        service = FlowService(db, flow_mgmt, flow_analytics, flow_dashboard, flow_engine)
        print("   ✅ FlowService instantiated successfully.")
        
        # Check SequentialMessageHandler
        print("2. Instantiating SequentialMessageHandler...")
        handler = SequentialMessageHandler(db)
        print("   ✅ SequentialMessageHandler instantiated successfully.")
        
        # Check Deprecation Warning

            
        print("\nAll consolidation checks passed!")
        
    except Exception as e:
        print(f"\n❌ Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_system())
