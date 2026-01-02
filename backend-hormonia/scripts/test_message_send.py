"""
Test script to verify message sending via async session and UnifiedWhatsAppService.
Run from backend-hormonia directory:
    venv\Scripts\python.exe scripts\test_message_send.py
"""
import asyncio
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_async_engine():
    """Test that async engine can be created and connect."""
    from app.core.database import get_async_session_factory, get_async_engine
    
    print("\n=== TEST 1: Async Engine Creation ===")
    try:
        engine = get_async_engine()
        print(f"OK Async engine created: {engine}")
    except Exception as e:
        print(f"FAIL Failed to create async engine: {e}")
        return False
    return True

async def test_async_session():
    """Test that async session can connect to DB."""
    from app.core.database import get_async_session_factory
    from sqlalchemy import text
    
    print("\n=== TEST 2: Async Session Connection ===")
    try:
        factory = get_async_session_factory()
        async with factory() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            print(f"OK Async session connected, test query result: {value}")
    except Exception as e:
        print(f"FAIL Failed to create async session: {e}")
        import traceback
        traceback.print_exc()
        return False
    return True

async def test_message_fetch():
    """Test that we can fetch a message from DB."""
    from app.core.database import get_async_session_factory
    from sqlalchemy import select
    from app.models.message import Message
    
    print("\n=== TEST 3: Fetch Latest Message ===")
    try:
        factory = get_async_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Message).order_by(Message.created_at.desc()).limit(1)
            )
            message = result.scalar_one_or_none()
            
            if message:
                print(f"OK Latest message fetched:")
                print(f"   ID: {message.id}")
                print(f"   Content: {message.content[:50] if message.content else 'None'}...")
                print(f"   Status: {message.status}")
                print(f"   Patient ID: {message.patient_id}")
                return message
            else:
                print("WARN No messages found in database")
                return None
    except Exception as e:
        print(f"FAIL Failed to fetch message: {e}")
        import traceback
        traceback.print_exc()
        return None

async def test_unified_whatsapp_service(message):
    """Test UnifiedWhatsAppService initialization and send."""
    from app.core.database import get_async_session_factory
    from app.services.unified_whatsapp_service import UnifiedWhatsAppService
    
    print("\n=== TEST 4: UnifiedWhatsAppService ===")
    try:
        factory = get_async_session_factory()
        async with factory() as session:
            # Refetch message in this session
            from sqlalchemy import select
            from app.models.message import Message
            
            result = await session.execute(
                select(Message).where(Message.id == message.id)
            )
            msg = result.scalar_one_or_none()
            
            if not msg:
                print(f"FAIL Message {message.id} not found")
                return False
            
            print(f"OK Creating UnifiedWhatsAppService...")
            service = UnifiedWhatsAppService(session)
            print(f"   Service mode: queue")
            print(f"   Default instance: {service.default_instance_name}")
            
            print(f"OK Calling send_message...")
            success = await service.send_message(msg)
            
            if success:
                print(f"OK Message send returned True!")
            else:
                print(f"WARN Message send returned False")
            return success
    except Exception as e:
        print(f"FAIL UnifiedWhatsAppService failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    print("=" * 60)
    print("MESSAGE SENDING TEST SCRIPT")
    print("=" * 60)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Test 1: Async engine
    if not await test_async_engine():
        print("\nFAIL: Cannot create async engine")
        return
    
    # Test 2: Async session
    if not await test_async_session():
        print("\nFAIL: Cannot create async session")
        return
    
    # Test 3: Fetch message
    message = await test_message_fetch()
    if not message:
        print("\nWARN No message to test with. Create a message first via frontend.")
        return
    
    # Test 4: Send message
    await test_unified_whatsapp_service(message)
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
